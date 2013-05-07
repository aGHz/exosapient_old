from .scraper import MBNA, BMO


def mbna(nr_statements):
    mbna = MBNA()
    mbna.load_snapshots()
    if nr_statements > 0:
        mbna.load_latest_statements()
    for i in range(1, nr_statements):
        mbna.load_statements(i)
    print mbna.__ansistr__()

def bmo():
    bmo = BMO()
    print bmo.__ansistr__()

