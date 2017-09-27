import sys

from pyscipopt import Model, quicksum, SCIP_PARAMSETTING
from datetime import datetime


def read_input_csv(filename):
    row_header, matrix, col_header = list(), dict(), set()
    with open(filename) as f:
        for csvline in f:
            csvline = csvline.strip()
            if len(row_header) == 0:
                row_header = csvline.split(',')
                continue
            row = csvline.split(',')
            for i in range(1, len(row)):
                matrix[row[0], row_header[i]] = float(row[i])
                col_header.add(row[0])
    row_header.pop(0)
    col_header = sorted(col_header)
    return matrix, row_header, col_header


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: InterviewScheduler Shortlists.csv SlotsPanels.csv Prefs.csv")
        exit(-1)
    print(datetime.now().time())
    shortlists, clubs, names = read_input_csv(sys.argv[1])
    print('Number of Clubs')
    print(len(clubs))
    print('Number of Candidates')
    print(len(names))
    panels, clubs2, slots = read_input_csv(sys.argv[2])
    print('Number of Slots')
    print(len(slots))

    prefs, clubs3, names2 = read_input_csv(sys.argv[3])
    assert (sorted(clubs) == sorted(clubs2))
    assert (sorted(clubs) == sorted(clubs3))
    assert (sorted(names) == sorted(names2))
    totalClubs = len(clubs) + 1

    costs = dict()

    maxpanels = dict()
    for c in clubs:
        maxpanels[c] = 0
        for s in slots:
            if panels[s, c] > maxpanels[c]:
                maxpanels[c] = panels[s, c]

    for s in range(len(slots)):
        costs[slots[s]] = s + 1

    print('Creating IPLP')

    m = Model()
    m.setPresolve(SCIP_PARAMSETTING.OFF)

    choices = {}
    for s in slots:
        for c in clubs:
            for n in names:
                name = str(s) + '_' + str(c) + '_' + str(n)
                choices[s, c, n] = m.addVar(name, vtype='B')

    totalstudents = sum(shortlists.values())

    # Objective - allocate max students to the initial few slots
    m.setObjective(
        quicksum(choices[s, c, n] * costs[s] * (totalClubs - prefs[n, c]) for s in slots for n in names for c in
                 clubs), "minimize")

    # Constraint all students to be allocated
    m.addCons(quicksum(choices[s, c, n] for s in slots for n in names for c in clubs) == totalstudents)

    # Constraint - maximum number in a slot for a club is limited by panels
    for c in clubs:
        for s in slots:
            m.addCons(quicksum(choices[s, c, n] for n in names) <= panels[s, c])

    # Constraint - allocate student only if he has a shortlist
    for n in names:
        for c in clubs:
            m.addCons(quicksum(choices[s, c, n] for s in slots) <= shortlists[n, c])

    # Constraint - slots should not conflict for a student
    for s in slots:
        for n in names:
            m.addCons(quicksum(choices[s, c, n] for c in clubs) <= 1)

    print('Begin optimisation')
    m.optimize()
    print(m.getStatus())

    schedout = open('schedule.csv', 'w')
    line = 'Slot'

    for c in clubs:
        for j in range(int(maxpanels[c])):
            line = line + ',' + c + str(j + 1)

    schedout.write(line + '\n')
    for s in slots:
        line = s
        for c in clubs:
            l = [''] * int(maxpanels[c])
            i = 0
            for n in names:
                if m.getVal(choices[s, c, n]) == 1:
                    l[i] = n + ' ' + str(prefs[n, c])
                    i = i + 1

            line = line + ',' + ','.join(l)

        schedout.write(line + '\n')

    schedout.close()

    print(datetime.now().time())
