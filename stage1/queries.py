import csv
from datetime import datetime, timedelta


class QueryEngine:

    def __init__(self):
        self.ds_records = []
        self.lb_records = []
        self.ae_records = []
        self.ex_records = []
        self.reference_ranges = []

    # =========================================================
    # DATE PARSING
    # =========================================================

    def parse_date(self, date_string):
        if not date_string:
            return None

        date_string = str(date_string).strip()

        formats = [
            "%Y-%m-%d",
            "%d-%b-%Y",
            "%d-%B-%Y"
        ]

        for fmt in formats:
            try:
                return datetime.strptime(
                    date_string, fmt
                ).date()
            except ValueError:
                continue

        return None

    # =========================================================
    # NUMBER PARSING
    # =========================================================

    def parse_number(self, value):
        """
        Handles:
        12.5  -> 12.5
        12,5  -> 12.5
        <5    -> 5.0
        ND    -> None
        empty -> None
        """

        if value is None:
            return None

        value = str(value).strip()

        if value == "":
            return None

        if value.upper() == "ND":
            return None

        # Example: <5
        if value.startswith("<"):
            value = value[1:].strip()

        # Example: 12,5
        value = value.replace(",", ".")

        try:
            return float(value)
        except ValueError:
            return None

    # =========================================================
    # CSV LOADING
    # =========================================================

    def load_csv(self, path):

        with open(
            path,
            newline="",
            encoding="utf-8"
        ) as file:

            return list(csv.DictReader(file))

    # =========================================================
    # LOAD ALL DATA
    # =========================================================

    def load_all(self, data_dir):

        self.ds_records = self.load_csv(
            f"{data_dir}/DS.csv"
        )

        self.lb_records = self.load_csv(
            f"{data_dir}/LB.csv"
        )

        self.ae_records = self.load_csv(
            f"{data_dir}/AE.csv"
        )

        self.ex_records = self.load_csv(
            f"{data_dir}/EX.csv"
        )

        self.reference_ranges = self.load_csv(
            f"{data_dir}/reference_ranges.csv"
        )

        print("DS records loaded:", len(self.ds_records))
        print("LB records loaded:", len(self.lb_records))
        print("AE records loaded:", len(self.ae_records))
        print("EX records loaded:", len(self.ex_records))
        print(
            "Reference ranges loaded:",
            len(self.reference_ranges)
        )

    # =========================================================
    # GET ULN
    # =========================================================

    def get_uln(self, test_code, unit, usubjid):

        parts = usubjid.split("-")

        site = ""

        if len(parts) >= 2:
            site = parts[1]

        # -----------------------------------------------------
        # First check site-specific laboratory range
        # -----------------------------------------------------

        for row in self.reference_ranges:

            if (
                row["LBTESTCD"].strip().upper()
                == test_code.strip().upper()
                and
                row["UNIT"].strip().lower()
                == unit.strip().lower()
                and
                row["LAB"].strip().upper()
                == site.strip().upper()
            ):

                return self.parse_number(
                    row["HIGH"]
                )

        # -----------------------------------------------------
        # Otherwise use CENTRAL laboratory range
        # -----------------------------------------------------

        for row in self.reference_ranges:

            if (
                row["LBTESTCD"].strip().upper()
                == test_code.strip().upper()
                and
                row["UNIT"].strip().lower()
                == unit.strip().lower()
                and
                row["LAB"].strip().upper()
                == "CENTRAL"
            ):

                return self.parse_number(
                    row["HIGH"]
                )

        return None

    # =========================================================
    # UNIT CONVERSION
    # =========================================================

    def convert_to_u_l(self, value, unit):

        if value is None:
            return None

        unit = unit.strip().lower()

        # ukat/L -> U/L
        if unit == "ukat/l":
            return value * 60.0

        # Already U/L
        if unit == "u/l":
            return value

        return value

    # =========================================================
    # COUNT QUERY
    # =========================================================

    def count_discontinued_ae(self, site=None):

        subjects = []
        evidence = []

        for row in self.ds_records:

            usubjid = row["USUBJID"]

            # -------------------------------------------------
            # Optional site filter
            # -------------------------------------------------

            if site is not None:

                if f"-{site}-" not in usubjid:
                    continue

            decision = (
                row["DSDECOD"]
                .strip()
                .upper()
            )

            reason = (
                row["DSTERM"]
                .strip()
                .upper()
            )

            # -------------------------------------------------
            # Discontinued due to adverse event
            # -------------------------------------------------

            if (
                decision == "DISCONTINUED"
                and
                reason == "ADVERSE EVENT"
            ):

                if usubjid not in subjects:

                    subjects.append(usubjid)

                evidence.append({
                    "domain": "DS",
                    "usubjid": usubjid,
                    "seq": int(row["DSSEQ"])
                })

        return (
            len(subjects),
            subjects,
            evidence
        )

    # =========================================================
    # LOOKUP QUERY
    # =========================================================

    def lookup_records(
        self,
        usubjid,
        visit,
        days=7
    ):

        visit_date = None

        # -----------------------------------------------------
        # Find visit date
        # -----------------------------------------------------

        for row in self.lb_records:

            if (
                row["USUBJID"] == usubjid
                and
                row["VISIT"].strip().upper()
                == visit.strip().upper()
            ):

                visit_date = self.parse_date(
                    row["LBDTC"]
                )

                if visit_date:
                    break

        if visit_date is None:

            return {
                "usubjid": usubjid,
                "visit": visit,
                "records": [],
                "evidence": []
            }

        start_date = (
            visit_date -
            timedelta(days=days)
        )

        end_date = (
            visit_date +
            timedelta(days=days)
        )

        records = []
        evidence = []

        # =====================================================
        # LAB RECORDS
        # =====================================================

        for row in self.lb_records:

            if row["USUBJID"] != usubjid:
                continue

            record_date = self.parse_date(
                row["LBDTC"]
            )

            if record_date is None:
                continue

            if (
                start_date
                <= record_date
                <= end_date
            ):

                records.append({
                    "domain": "LB",
                    "seq": int(row["LBSEQ"]),
                    "date": row["LBDTC"],
                    "visit": row["VISIT"],
                    "test": row["LBTESTCD"],
                    "value": row["LBORRES"],
                    "unit": row["LBORRESU"]
                })

                evidence.append({
                    "domain": "LB",
                    "usubjid": usubjid,
                    "seq": int(row["LBSEQ"])
                })

        # =====================================================
        # ADVERSE EVENT RECORDS
        # =====================================================

        for row in self.ae_records:

            if row["USUBJID"] != usubjid:
                continue

            record_date = self.parse_date(
                row["AESTDTC"]
            )

            if record_date is None:
                continue

            if (
                start_date
                <= record_date
                <= end_date
            ):

                records.append({
                    "domain": "AE",
                    "seq": int(row["AESEQ"]),
                    "date": row["AESTDTC"],
                    "term": row["AETERM"],
                    "severity": row["AESEV"],
                    "serious": row["AESER"]
                })

                evidence.append({
                    "domain": "AE",
                    "usubjid": usubjid,
                    "seq": int(row["AESEQ"])
                })

        # -----------------------------------------------------
        # Sort records by date
        # -----------------------------------------------------

        records.sort(
            key=lambda x: (
                self.parse_date(x["date"])
                or datetime.min.date()
            )
        )

        return {
            "usubjid": usubjid,
            "visit": visit,
            "visit_date": str(visit_date),
            "window_start": str(start_date),
            "window_end": str(end_date),
            "records": records,
            "evidence": evidence
        }

    # =========================================================
    # FINDING QUERY - HY'S LAW
    # =========================================================

    def find_hys_law_candidates(self):

        # -----------------------------------------------------
        # Group laboratory records by subject
        # -----------------------------------------------------

        subject_labs = {}

        for row in self.lb_records:

            usubjid = row["USUBJID"]

            if usubjid not in subject_labs:
                subject_labs[usubjid] = []

            subject_labs[usubjid].append(row)

        candidates = []
        candidate_evidence = {}

        # =====================================================
        # Check each subject
        # =====================================================

        for usubjid, labs in subject_labs.items():

            liver_records = []
            bilirubin_records = []

            # =================================================
            # ALT / AST
            # =================================================

            for row in labs:

                test = (
                    row["LBTESTCD"]
                    .strip()
                    .upper()
                )

                if test not in ["ALT", "AST"]:
                    continue

                value = self.parse_number(
                    row["LBORRES"]
                )

                if value is None:
                    continue

                unit = row["LBORRESU"].strip()

                uln = self.get_uln(
                    test,
                    unit,
                    usubjid
                )

                if uln is None:
                    continue

                converted_value = (
                    self.convert_to_u_l(
                        value,
                        unit
                    )
                )

                converted_uln = (
                    self.convert_to_u_l(
                        uln,
                        unit
                    )
                )

                if converted_value is None:
                    continue

                if converted_uln is None:
                    continue

                # ---------------------------------------------
                # ALT / AST > 3 × ULN
                # ---------------------------------------------

                if (
                    converted_value
                    > 3 * converted_uln
                ):

                    liver_records.append({
                        "row": row,
                        "date": self.parse_date(
                            row["LBDTC"]
                        ),
                        "test": test
                    })

            # =================================================
            # BILIRUBIN
            # =================================================

            for row in labs:

                test = (
                    row["LBTESTCD"]
                    .strip()
                    .upper()
                )

                if test != "BILI":
                    continue

                value = self.parse_number(
                    row["LBORRES"]
                )

                if value is None:
                    continue

                unit = row["LBORRESU"].strip()

                uln = self.get_uln(
                    test,
                    unit,
                    usubjid
                )

                if uln is None:
                    continue

                converted_value = (
                    self.convert_to_u_l(
                        value,
                        unit
                    )
                )

                converted_uln = (
                    self.convert_to_u_l(
                        uln,
                        unit
                    )
                )

                if converted_value is None:
                    continue

                if converted_uln is None:
                    continue

                # ---------------------------------------------
                # Bilirubin > 2 × ULN
                # ---------------------------------------------

                if (
                    converted_value
                    > 2 * converted_uln
                ):

                    bilirubin_records.append({
                        "row": row,
                        "date": self.parse_date(
                            row["LBDTC"]
                        )
                    })

            # =================================================
            # CHECK 14-DAY WINDOW
            # =================================================

            found = False
            evidence = []

            for liver in liver_records:

                liver_date = liver["date"]

                if liver_date is None:
                    continue

                for bili in bilirubin_records:

                    bili_date = bili["date"]

                    if bili_date is None:
                        continue

                    difference = abs(
                        (
                            liver_date -
                            bili_date
                        ).days
                    )

                    if difference <= 14:

                        found = True

                        # -------------------------------------
                        # Liver evidence
                        # -------------------------------------

                        evidence.append({
                            "domain": "LB",
                            "usubjid": usubjid,
                            "seq": int(
                                liver["row"]["LBSEQ"]
                            )
                        })

                        # -------------------------------------
                        # Bilirubin evidence
                        # -------------------------------------

                        evidence.append({
                            "domain": "LB",
                            "usubjid": usubjid,
                            "seq": int(
                                bili["row"]["LBSEQ"]
                            )
                        })

                        break

                if found:
                    break

            if found:

                candidates.append(usubjid)

                candidate_evidence[
                    usubjid
                ] = evidence

        return (
            candidates,
            candidate_evidence
        )

    # =========================================================
    # TRAP QUERY - WRONG DOSE
    # =========================================================

    def find_wrong_doses(self, site):

        wrong_subjects = []
        evidence = []

        for row in self.ex_records:

            usubjid = row["USUBJID"]

            # -------------------------------------------------
            # Check site
            #
            # Example:
            # 042-S01-001
            #       ^^^
            #       S01
            # -------------------------------------------------

            if f"-{site}-" not in usubjid:
                continue

            treatment = (
                row["EXTRT"]
                .strip()
                .upper()
            )

            dose = self.parse_number(
                row["EXDOSE"]
            )

            # Missing dose -> skip safely
            if dose is None:
                continue

            # =================================================
            # PROTOCOL SECTION 8
            # =================================================

            if treatment == "DRUG":

                correct_dose = 10.0

            elif treatment == "PLACEBO":

                correct_dose = 0.0

            else:
                # Unknown treatment
                continue

            # =================================================
            # CHECK DOSING ERROR
            # =================================================

            if dose != correct_dose:

                if usubjid not in wrong_subjects:

                    wrong_subjects.append(
                        usubjid
                    )

                evidence.append({
                    "domain": "EX",
                    "usubjid": usubjid,
                    "seq": int(row["EXSEQ"])
                })

        return (
            wrong_subjects,
            evidence
        )


# =============================================================
# MAIN PROGRAM
# =============================================================

if __name__ == "__main__":

    # IMPORTANT:
    # Run from project root using:
    #
    # python stage1/queries.py
    #
    # Therefore this path is:
    # E:\ATLAS-Study-Graph\hackathon-data\data

    DATA_DIR = "hackathon-data/data"

    # ---------------------------------------------------------
    # Create query engine
    # ---------------------------------------------------------

    engine = QueryEngine()

    # ---------------------------------------------------------
    # Load data
    # ---------------------------------------------------------

    engine.load_all(DATA_DIR)

    # =========================================================
    # COUNT QUERY
    # =========================================================

    print()
    print("=" * 60)
    print("COUNT QUERY")
    print("=" * 60)

    count, subjects, evidence = (
        engine.count_discontinued_ae()
    )

    print(
        "Number of subjects:",
        count
    )

    print()
    print("Subjects:")

    for subject in subjects:
        print(subject)

    print()
    print("Evidence:")

    for item in evidence:
        print(item)

    # =========================================================
    # LOOKUP QUERY
    # =========================================================

    print()
    print("=" * 60)
    print("LOOKUP QUERY")
    print("=" * 60)

    result = engine.lookup_records(
        "042-S05-003",
        "WEEK8",
        7
    )

    print(
        "Subject:",
        result["usubjid"]
    )

    print(
        "Visit:",
        result["visit"]
    )

    print(
        "Visit date:",
        result.get("visit_date")
    )

    print(
        "7-day window:",
        result.get("window_start"),
        "to",
        result.get("window_end")
    )

    print()
    print("Records:")

    for record in result["records"]:
        print(record)

    print()
    print("Evidence:")

    for item in result["evidence"]:
        print(item)

    # =========================================================
    # FINDING QUERY
    # =========================================================

    print()
    print("=" * 60)
    print("FINDING QUERY - HY'S LAW")
    print("=" * 60)

    candidates, evidence = (
        engine.find_hys_law_candidates()
    )

    print(
        "Hy's law candidates:",
        candidates
    )

    print()
    print("Evidence:")

    for subject in candidates:

        print()
        print(subject)

        for item in evidence[subject]:
            print(item)

    # =========================================================
    # TRAP QUERY
    # =========================================================

    print()
    print("=" * 60)
    print("TRAP QUERY - WRONG DOSE AT S01")
    print("=" * 60)

    wrong, evidence = (
        engine.find_wrong_doses("S01")
    )

    print(
        "Wrong-dose subjects:",
        wrong
    )

    print(
        "Evidence:",
        evidence
    )