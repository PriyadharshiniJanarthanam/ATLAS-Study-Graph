import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path


@dataclass
class ReviewReport:
    cut: int
    protocol_version: int
    findings: list = field(default_factory=list)
    escalations: list = field(default_factory=list)
    queries: list = field(default_factory=list)
    deviations: list = field(default_factory=list)
    trace: list = field(default_factory=list)
    approved_actions: list = field(default_factory=list)

    @property
    def summary(self):
        return {
            "cut": self.cut,
            "protocol_version": self.protocol_version,
            "findings": len(self.findings),
            "escalations": len(self.escalations),
            "queries": len(self.queries),
            "deviations": len(self.deviations),
            "trace_entries": len(self.trace),
            "approved_actions": len(self.approved_actions),
        }


class ReviewCrew:

    def __init__(self, hub_url, gateway_url, team_key, atlas):
        self.hub_url = hub_url
        self.gateway_url = gateway_url
        self.team_key = team_key
        self.atlas = atlas

        # Memory across cycles
        self.raised_queries = set()
        self.raised_escalations = set()
        self.rejected_escalations = set()
        self.open_queries = set()
        self.subject_flags = {}
        self.site_flags = {}

        # Human gate decisions
        self.human_decisions = {}

        # Protocol cache
        self.protocol_cache = {}

    # ---------------------------------------------------------
    # GET DOMAIN FROM STUDY GRAPH
    # ---------------------------------------------------------
    def _get_domain(self, domain):
        mapping = {
            "DM": "dm",
            "AE": "ae",
            "LB": "lb",
            "VS": "vs",
            "EX": "ex",
            "CM": "cm",
            "DS": "ds",
            "MH": "mh",
            "EG": "eg",
        }

        attribute = mapping.get(domain)

        if attribute is None:
            return []

        return getattr(self.atlas.graph, attribute, []) or []

    # ---------------------------------------------------------
    # TRACE
    # ---------------------------------------------------------
    def _trace(self, trace, node, action, decision, evidence=None):

        entry = {
            "time": datetime.now().isoformat(),
            "node": node,
            "action": action,
            "decision": decision,
            "evidence": evidence or [],
        }

        trace.append(entry)

    # ---------------------------------------------------------
    # EVIDENCE
    # ---------------------------------------------------------
    def _evidence(self, domain, record):
        return [{
            "domain": domain,
            "usubjid": str(
                record.get("USUBJID", record.get("usubjid", ""))
            ),
            "seq": str(
                record.get(
                    f"{domain}SEQ",
                    record.get("seq", record.get("AESEQ", ""))
                )
            )
        }]

    # ---------------------------------------------------------
    # CUT CHECK
    # ---------------------------------------------------------
    def _available_at_cut(self, record, cut):

        value = record.get("cut_available", "")

        if value in ("", None):
            return True

        try:
            return int(value) <= int(cut)
        except Exception:
            return True

    # ---------------------------------------------------------
    # DATE PARSER
    # ---------------------------------------------------------
    def _date(self, value):

        if not value:
            return None

        try:
            return datetime.fromisoformat(str(value)).date()
        except Exception:
            return None

    # ---------------------------------------------------------
    # FIRST DOSE
    # ---------------------------------------------------------
    def _first_dose(self, usubjid, cut):

        ex_records = self._get_domain("EX")

        dates = []

        for record in ex_records:

            subject = str(
                record.get("USUBJID", record.get("usubjid", ""))
            )

            if subject != str(usubjid):
                continue

            if not self._available_at_cut(record, cut):
                continue

            for key in [
                "EXSTDTC",
                "EX_START",
                "START_DATE",
                "EXDTC"
            ]:

                if record.get(key):
                    date = self._date(record.get(key))

                    if date:
                        dates.append(date)

        if not dates:
            return None

        return min(dates)

    # ---------------------------------------------------------
    # DETECT
    # ---------------------------------------------------------
    def _detect(self, cut, protocol_version, trace):

        findings = []

        ae_records = self._get_domain("AE")

        # -----------------------------------------------------
        # AE DETECTION
        # -----------------------------------------------------
        for record in ae_records:

            if not self._available_at_cut(record, cut):
                continue

            usubjid = str(record.get("USUBJID", ""))
            site = usubjid[4:7] if len(usubjid) >= 7 else ""

            term = str(record.get("AETERM", "Unknown"))

            aeser = str(record.get("AESER", "")).upper()
            aeshosp = str(record.get("AESHOSP", "")).upper()

            evidence = self._evidence("AE", record)

            # -------------------------------------------------
            # SERIOUS AE
            # Protocol: AESHOSP=Y means serious even if AESER=N
            # -------------------------------------------------
            if aeser == "Y" or aeshosp == "Y":

                if aeshosp == "Y" and aeser != "Y":

                    findings.append({
                        "code": "SAE_MISCODED",
                        "usubjid": usubjid,
                        "site": site,
                        "severity": "CRITICAL",
                        "rationale": (
                            f"'{term}' has AESHOSP=Y but AESER=N"
                        ),
                        "evidence": evidence,
                    })

                else:

                    findings.append({
                        "code": "SERIOUS_AE",
                        "usubjid": usubjid,
                        "site": site,
                        "severity": "CRITICAL",
                        "rationale": (
                            f"'{term}' is recorded as a serious "
                            f"adverse event"
                        ),
                        "evidence": evidence,
                    })

            # -------------------------------------------------
            # AE BEFORE FIRST DOSE
            # -------------------------------------------------
            ae_start = self._date(record.get("AESTDTC"))

            first_dose = self._first_dose(usubjid, cut)

            if ae_start and first_dose and ae_start < first_dose:

                findings.append({
                    "code": "AE_BEFORE_FIRST_DOSE",
                    "usubjid": usubjid,
                    "site": site,
                    "severity": "HIGH",
                    "rationale": (
                        f"AE '{term}' starts {ae_start}, "
                        f"before first dose {first_dose}"
                    ),
                    "evidence": evidence,
                })

        # -----------------------------------------------------
        # SUBJECT MEMORY
        # -----------------------------------------------------
        for finding in findings:

            subject = finding["usubjid"]

            self.subject_flags.setdefault(subject, 0)
            self.subject_flags[subject] += 1

        self._trace(
            trace,
            "detect",
            "scan",
            f"{len(findings)} findings detected under protocol "
            f"v{protocol_version} at cut {cut}",
            [
                evidence
                for finding in findings
                for evidence in finding.get("evidence", [])
            ]
        )

        return findings

    # ---------------------------------------------------------
    # MEDICAL REVIEW
    # ---------------------------------------------------------
    def _medical_review(self, findings, trace):

        escalations = []

        for finding in findings:

            code = finding.get("code", "")

            # Data-quality findings go to Data Manager.
            if code in {
                "AE_BEFORE_FIRST_DOSE",
                "MISSING_DOSE",
                "UNIT_MISMATCH",
                "DUPLICATE_SUBJECT",
            }:
                continue

            # Only medical/safety findings reach escalation.
            if code in {
                "SAE_MISCODED",
                "SERIOUS_AE",
                "HYS_LAW",
            }:

                subject = finding["usubjid"]

                # Rejected escalation should not be raised again.
                if subject in self.rejected_escalations:
                    continue

                # Do not duplicate escalation.
                if subject in self.raised_escalations:
                    continue

                escalation = {
                    "code": finding["code"],
                    "usubjid": subject,
                    "severity": finding["severity"],
                    "summary": finding["rationale"],
                    "evidence": finding["evidence"],
                    "alternatives": [
                        "Approve escalation",
                        "Reject and downgrade to monitoring",
                        "Request clarification",
                    ],
                }

                escalations.append(escalation)
                self.raised_escalations.add(subject)

        self._trace(
            trace,
            "medical_review",
            "review",
            f"{len(escalations)} escalation drafts created",
            [
                evidence
                for escalation in escalations
                for evidence in escalation.get("evidence", [])
            ]
        )

        return escalations

    # ---------------------------------------------------------
    # DATA MANAGER
    # ---------------------------------------------------------
    def _data_manager(self, findings, cut, trace):

        queries = []

        for finding in findings:

            code = finding.get("code", "")

            if code not in {
                "AE_BEFORE_FIRST_DOSE",
                "MISSING_DOSE",
                "UNIT_MISMATCH",
                "DUPLICATE_SUBJECT",
            }:
                continue

            subject = finding["usubjid"]

            evidence = finding.get("evidence", [])

            if evidence:
                first = evidence[0]

                key = (
                    first.get("domain"),
                    first.get("usubjid"),
                    first.get("seq"),
                )
            else:
                key = (code, subject)

            # Existing query remains open.
            if key in self.raised_queries:
                continue

            query = {
                "usubjid": subject,
                "domain": evidence[0]["domain"] if evidence else "",
                "seq": evidence[0]["seq"] if evidence else "",
                "cut": cut,
                "code": code,
                "text": finding["rationale"],
                "evidence": evidence,
                "status": "OPEN",
            }

            queries.append(query)

            self.raised_queries.add(key)
            self.open_queries.add(key)

        self._trace(
            trace,
            "data_manager",
            "create_queries",
            f"{len(queries)} new queries",
            [
                evidence
                for query in queries
                for evidence in query.get("evidence", [])
            ]
        )

        return queries

    # ---------------------------------------------------------
    # COMPLIANCE
    # ---------------------------------------------------------
    def _compliance(self, findings, cut, protocol_version, trace):

        deviations = []

        # Basic protocol-version check.
        #
        # This is intentionally conservative. Findings are not
        # automatically considered protocol deviations unless
        # they represent an actual compliance problem.
        for finding in findings:

            code = finding.get("code", "")

            if code == "AE_BEFORE_FIRST_DOSE":

                deviations.append({
                    "usubjid": finding["usubjid"],
                    "code": "PRE_DOSE_AE",
                    "protocol_version": protocol_version,
                    "cut": cut,
                    "reason": finding["rationale"],
                    "evidence": finding["evidence"],
                })

        self._trace(
            trace,
            "compliance",
            "protocol_check",
            f"{len(deviations)} deviations under protocol "
            f"v{protocol_version}",
            [
                evidence
                for deviation in deviations
                for evidence in deviation.get("evidence", [])
            ]
        )

        return deviations

    # ---------------------------------------------------------
    # HUMAN DECISION
    # ---------------------------------------------------------

    def _answer_clarification(self, escalation):
        subject = escalation["usubjid"]

        patient = self.atlas.graph.patient_data.get(subject, {})

        answer = {
            "screening_alt": None,
            "screening_ast": None,
            "screening_bili": None,
            "hepatotoxic_conmeds": []
        }

        # Find screening lab values
        for record in patient.get("LB", []):
            if record.get("VISIT") == "SCREENING":
                test = record.get("LBTESTCD")

                if test == "ALT":
                    answer["screening_alt"] = record.get("LBORRES")

                elif test == "AST":
                    answer["screening_ast"] = record.get("LBORRES")

                elif test == "BILI":
                    answer["screening_bili"] = record.get("LBORRES")

        # Check concomitant medicines
        known_hepatotoxic = {
            "PARACETAMOL",
            "ACETAMINOPHEN",
            "ISONIAZID",
            "RIFAMPICIN"
        }

        for record in patient.get("CM", []):
            medicine = str(record.get("CMTRT", "")).upper()

            if medicine in known_hepatotoxic:
                answer["hepatotoxic_conmeds"].append(
                    record.get("CMTRT")
                )

        return answer
    def set_human_decision(self, escalation_code, decision, reason=""):

        decision = str(decision).upper()

        if decision not in {
            "APPROVED",
            "REJECTED",
            "CLARIFY",
        }:
            raise ValueError(
                "Decision must be APPROVED, REJECTED, or CLARIFY"
            )

        self.human_decisions[escalation_code] = {
            "decision": decision,
            "reason": reason,
        }

    # ---------------------------------------------------------
    # HUMAN GATE
    # ---------------------------------------------------------
    def _human_gate(self, escalations, trace):

        approved = []
        rejected = []
        clarify = []
        pending = []

        for escalation in escalations:

            code = escalation["code"]
            subject = escalation["usubjid"]

            key = f"{code}:{subject}"

            decision_data = self.human_decisions.get(key)

            # No decision yet.
            if decision_data is None:

                pending.append(escalation)
                continue

            decision = decision_data["decision"]
            reason = decision_data.get("reason", "")

            if decision == "APPROVED":

                approved.append({
                    "escalation": escalation,
                    "decision": "APPROVED",
                    "reason": reason,
                })

                self.raised_escalations.add(subject)

            elif decision == "REJECTED":

                rejected.append({
                    "escalation": escalation,
                    "decision": "REJECTED",
                    "reason": reason,
                })

                self.rejected_escalations.add(subject)

            elif decision == "CLARIFY":

                clarify.append({
                    "escalation": escalation,
                    "decision": "CLARIFY",
                    "reason": reason,
                })

        evidence = [
            evidence
            for item in (
                approved + rejected + clarify + pending
            )
            for evidence in (
                item.get("escalation", item).get("evidence", [])
            )
        ]

        self._trace(
            trace,
            "human_gate",
            "review",
            (
                f"approved={len(approved)}, "
                f"rejected={len(rejected)}, "
                f"clarify={len(clarify)}, "
                f"pending={len(pending)}"
            ),
            evidence
        )

        return {
            "approved": approved,
            "rejected": rejected,
            "clarify": clarify,
            "pending": pending,
        }

    # ---------------------------------------------------------
    # EXECUTE
    # ---------------------------------------------------------
    def _execute(self, gate_result, trace):

        approved_actions = []

        for item in gate_result["approved"]:

            escalation = item["escalation"]

            approved_actions.append({
                "usubjid": escalation["usubjid"],
                "code": escalation["code"],
                "action": "EXECUTE_ESCALATION",
                "reason": item.get("reason", ""),
                "evidence": escalation.get("evidence", []),
            })

        self._trace(
            trace,
            "execute",
            "complete",
            (
                f"Cycle execution completed: "
                f"{len(approved_actions)} approved actions"
            ),
            [
                evidence
                for action in approved_actions
                for evidence in action.get("evidence", [])
            ]
        )

        return approved_actions

    # ---------------------------------------------------------
    # RUN CYCLE
    # ---------------------------------------------------------
    def run_cycle(self, cut: int, protocol_version: int):

        trace = []

        # 1. DETECT
        findings = self._detect(
            cut,
            protocol_version,
            trace
        )

        # 2. MEDICAL REVIEW
        escalations = self._medical_review(
            findings,
            trace
        )

        # 3. DATA MANAGER
        queries = self._data_manager(
            findings,
            cut,
            trace
        )

        # 4. COMPLIANCE
        deviations = self._compliance(
            findings,
            cut,
            protocol_version,
            trace
        )

        # 5. HUMAN GATE
        gate_result = self._human_gate(
            escalations,
            trace
        )

        # 6. EXECUTE
        approved_actions = self._execute(
            gate_result,
            trace
        )

        report = ReviewReport(
            cut=cut,
            protocol_version=protocol_version,
            findings=findings,
            escalations=escalations,
            queries=queries,
            deviations=deviations,
            trace=trace,
            approved_actions=approved_actions,
        )

        return report


