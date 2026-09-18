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

    def load_csv(self, filename):
        path = os.path.join(self.data_dir, filename)

        with open(path, "r", encoding="utf-8-sig") as file:
            return list(csv.DictReader(file))

    def build(self):
        print("Loading study data...")

        self.dm = self.load_csv("DM.csv")
        self.ae = self.load_csv("AE.csv")
        self.lb = self.load_csv("LB.csv")
        self.vs = self.load_csv("VS.csv")
        self.ex = self.load_csv("EX.csv")
        self.cm = self.load_csv("CM.csv")
        self.ds = self.load_csv("DS.csv")
        self.mh = self.load_csv("MH.csv")
        self.eg = self.load_csv("EG.csv")

        print("DM:", len(self.dm))
        print("AE:", len(self.ae))
        print("LB:", len(self.lb))
        print("VS:", len(self.vs))
        print("EX:", len(self.ex))
        print("CM:", len(self.cm))
        print("DS:", len(self.ds))
        print("MH:", len(self.mh))
        print("EG:", len(self.eg))

        # Create Patient 360
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

        # Connect records to patients
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

        print("Patient 360 created:", len(self.patient_data))

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

if __name__ == "__main__":

    data_path = "../hackathon-data/data"

    graph = StudyGraph(data_path)

    stats = graph.build()

    print(stats)

    patient = graph.patient360("042-S01-001")

    print("Patient:", patient["DM"]["USUBJID"])
    print("AE records:", len(patient["AE"]))
    print("LB records:", len(patient["LB"]))
    print("VS records:", len(patient["VS"]))
    print("EX records:", len(patient["EX"]))
    print("CM records:", len(patient["CM"]))
    print("DS records:", len(patient["DS"]))
    print("MH records:", len(patient["MH"]))
    print("EG records:", len(patient["EG"]))