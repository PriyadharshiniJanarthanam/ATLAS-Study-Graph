import csv
import os


class StudyGraph:

    def __init__(self, data_dir):

        self.data_dir = data_dir

        self.dm = []
        self.ae = []
        self.lb = []
        self.vs = []
        self.ex = []
        self.cm = []
        self.ds = []
        self.mh = []
        self.eg = []

        self.patient_data = {}

        self.indexes = {
            "DM": {},
            "AE": {},
            "LB": {},
            "VS": {},
            "EX": {},
            "CM": {},
            "DS": {},
            "MH": {},
            "EG": {}
        }

    def load_csv(self, filename):

        path = os.path.join(self.data_dir, filename)

        with open(path, "r", encoding="utf-8-sig") as file:
            return list(csv.DictReader(file))

    def filter_by_cut(self, records, cut):

        if cut is None:
            return records

        filtered = []

        for record in records:

            value = record.get("cut_available", "")

            if value != "" and int(value) <= cut:
                filtered.append(record)

        return filtered

    def build_indexes(self):

        print("\nBuilding indexes...")

        for record in self.dm:

            usubjid = record["USUBJID"]

            self.indexes["DM"][usubjid] = record

        domains = {
            "AE": self.ae,
            "LB": self.lb,
            "VS": self.vs,
            "EX": self.ex,
            "CM": self.cm,
            "DS": self.ds,
            "MH": self.mh,
            "EG": self.eg
        }

        for domain, records in domains.items():

            for record in records:

                usubjid = record["USUBJID"]

                if usubjid not in self.indexes[domain]:
                    self.indexes[domain][usubjid] = []

                self.indexes[domain][usubjid].append(record)

        print("Indexes created.")

    def build(self, cut=None):

        print("Loading study data...")

        if cut is not None:
            print("Using cut:", cut)

        self.dm = self.load_csv("DM.csv")
        self.ae = self.load_csv("AE.csv")
        self.lb = self.load_csv("LB.csv")
        self.vs = self.load_csv("VS.csv")
        self.ex = self.load_csv("EX.csv")
        self.cm = self.load_csv("CM.csv")
        self.ds = self.load_csv("DS.csv")
        self.mh = self.load_csv("MH.csv")
        self.eg = self.load_csv("EG.csv")

        print("\nOriginal records:")

        print("DM:", len(self.dm))
        print("AE:", len(self.ae))
        print("LB:", len(self.lb))
        print("VS:", len(self.vs))
        print("EX:", len(self.ex))
        print("CM:", len(self.cm))
        print("DS:", len(self.ds))
        print("MH:", len(self.mh))
        print("EG:", len(self.eg))

        self.dm = self.filter_by_cut(self.dm, cut)
        self.ae = self.filter_by_cut(self.ae, cut)
        self.lb = self.filter_by_cut(self.lb, cut)
        self.vs = self.filter_by_cut(self.vs, cut)
        self.ex = self.filter_by_cut(self.ex, cut)
        self.cm = self.filter_by_cut(self.cm, cut)
        self.ds = self.filter_by_cut(self.ds, cut)
        self.mh = self.filter_by_cut(self.mh, cut)
        self.eg = self.filter_by_cut(self.eg, cut)

        self.patient_data = {}

        for domain in self.indexes:
            self.indexes[domain] = {}

        for subject in self.dm:

            usubjid = subject["USUBJID"]

            self.patient_data[usubjid] = {
                "DM": subject,
                "AE": [],
                "LB": [],
                "VS": [],
                "EX": [],
                "CM": [],
                "DS": [],
                "MH": [],
                "EG": []
            }

        domains = {
            "AE": self.ae,
            "LB": self.lb,
            "VS": self.vs,
            "EX": self.ex,
            "CM": self.cm,
            "DS": self.ds,
            "MH": self.mh,
            "EG": self.eg
        }

        for domain, records in domains.items():

            for record in records:

                usubjid = record["USUBJID"]

                if usubjid in self.patient_data:
                    self.patient_data[usubjid][domain].append(record)

        self.build_indexes()

        print("\nPatient 360 created:", len(self.patient_data))

        return {
            "DM": len(self.dm),
            "AE": len(self.ae),
            "LB": len(self.lb),
            "VS": len(self.vs),
            "EX": len(self.ex),
            "CM": len(self.cm),
            "DS": len(self.ds),
            "MH": len(self.mh),
            "EG": len(self.eg),
            "patients": len(self.patient_data)
        }

    def patient360(self, usubjid):

        if usubjid not in self.patient_data:
            return {}

        return self.patient_data[usubjid]

    def get_patient_records(self, usubjid):

        if usubjid not in self.indexes["DM"]:
            return {}

        return {
            "DM": self.indexes["DM"].get(usubjid),
            "AE": self.indexes["AE"].get(usubjid, []),
            "LB": self.indexes["LB"].get(usubjid, []),
            "VS": self.indexes["VS"].get(usubjid, []),
            "EX": self.indexes["EX"].get(usubjid, []),
            "CM": self.indexes["CM"].get(usubjid, []),
            "DS": self.indexes["DS"].get(usubjid, []),
            "MH": self.indexes["MH"].get(usubjid, []),
            "EG": self.indexes["EG"].get(usubjid, [])
        }


if __name__ == "__main__":

    data_path = "../hackathon-data/data"

    graph = StudyGraph(data_path)

    stats = graph.build()

    print("\nFinal statistics:")
    print(stats)

    patient_id = "042-S01-001"

    patient = graph.patient360(patient_id)

    if patient:

        print("\nPatient 360:", patient_id)

        print("AE:", len(patient["AE"]))
        print("LB:", len(patient["LB"]))
        print("VS:", len(patient["VS"]))
        print("EX:", len(patient["EX"]))
        print("CM:", len(patient["CM"]))
        print("DS:", len(patient["DS"]))
        print("MH:", len(patient["MH"]))
        print("EG:", len(patient["EG"]))

    records = graph.get_patient_records(patient_id)

    print("\nFast lookup test:")

    if records:

        print("Patient found!")
        print("Labs:", len(records["LB"]))
        print("Vitals:", len(records["VS"]))
        print("Exposure:", len(records["EX"]))

    else:

        print("Patient not found.")