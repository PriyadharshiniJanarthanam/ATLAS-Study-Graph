import re
import sys
from pathlib import Path

try:
    from .study_graph import StudyGraph
except ImportError:
    from study_graph import StudyGraph

try:
    from stage1.queries import QueryEngine
except ImportError:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from stage1.queries import QueryEngine


class Atlas:

    def __init__(self, graph):
        self.graph = graph
        self.engine = QueryEngine()
        self.engine.ds_records = graph.ds
        self.engine.lb_records = graph.lb
        self.engine.ae_records = graph.ae
        self.engine.ex_records = graph.ex
        ranges_path = Path(graph.data_dir) / "reference_ranges.csv"
        if ranges_path.exists():
            self.engine.reference_ranges = self.engine.load_csv(str(ranges_path))

    def answer(self, question):
        q = str(question).strip().lower()

        if "how many subjects" in q and "discontinu" not in q:
            return {
                "answer": len(self.graph.patient_data),
                "evidence": [
                    {"domain": "DM", "usubjid": usubjid, "seq": 1}
                    for usubjid in self.graph.patient_data
                ],
            }

        if "discontinu" in q or ("count" in q and "adverse event" in q):
            count, subjects, evidence = self.engine.count_discontinued_ae()
            return {
                "answer": count,
                "subjects": subjects,
                "evidence": self._valid_evidence(evidence)
            }

        lookup = re.search(
            r"(?:subject|usubjid)\s+([0-9A-Za-z-]+).*?"
            r"(?:visit\s+)?(screening|baseline|week\d+|end of study)",
            q,
        )
        if lookup:
            result = self.engine.lookup_records(
                lookup.group(1).upper(),
                lookup.group(2).upper(),
            )
            result["evidence"] = self._valid_evidence(result["evidence"])
            return result

        if "hy" in q and "law" in q:
            subjects, evidence = self.engine.find_hys_law_candidates()
            return {
                "answer": subjects,
                "evidence": {
                    subject: self._valid_evidence(refs)
                    for subject, refs in evidence.items()
                },
            }

        if "wrong" in q and "dose" in q:
            site_match = re.search(r"\b(s\d{2})\b", q)
            site = site_match.group(1).upper() if site_match else None
            if site is None:
                return {"answer": [], "evidence": []}
            subjects, evidence = self.engine.find_wrong_doses(site)
            return {
                "answer": subjects,
                "evidence": self._valid_evidence(evidence),
            }

        return {
            "answer": [],
            "evidence": []
        }

    def _valid_evidence(self, references):
        valid = []
        for reference in references:
            domain = reference.get("domain", "").upper()
            subject = reference.get("usubjid")
            try:
                seq = int(reference.get("seq"))
            except (TypeError, ValueError):
                continue
            rows = self.graph.indexes.get(domain, {}).get(subject, [])
            if domain == "DM":
                exists = bool(rows) and str(rows.get("USUBJID")) == subject
            else:
                exists = any(str(row.get(f"{domain}SEQ")) == str(seq) for row in rows)
            if exists:
                valid.append({"domain": domain, "usubjid": subject, "seq": seq})
        return valid


if __name__ == "__main__":

    data_path = Path(__file__).resolve().parents[1] / "hackathon-data" / "data"
    graph = StudyGraph(str(data_path))
    graph.build()

    atlas = Atlas(graph)

    result = atlas.answer("How many subjects are there?")

    print("ANSWER:")
    print(result["answer"])

    print("EVIDENCE:")
    print(result["evidence"])