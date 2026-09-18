import csv
import os


class StudyGraph:

    def __init__(self, data_dir):
        self.data_dir = data_dir
        self.subjects = []

    def load_csv(self, filename):
        path = os.path.join(self.data_dir, filename)

        with open(path, "r", encoding="utf-8-sig") as file:
            return list(csv.DictReader(file))

    def build(self):
        print("Loading study data...")

        self.subjects = self.load_csv("DM.csv")

        print("Subjects loaded:", len(self.subjects))

        return {
            "subjects": len(self.subjects)
        }


if __name__ == "__main__":
    data_path = "../hackathon-data/data"

    graph = StudyGraph(data_path)

    stats = graph.build()

    print(stats)