from pulp import *
import sys
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
            col_header.add(row[0])
            for i in range(1, len(row)):
                matrix[row[0], row_header[i]] = float(row[i])

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

    # Find out max number of panels
    maxpanels = dict((c, max(panels[s, c] for s in slots)) for c in clubs)

    # Generate cost of slots
    costs = dict((slots[s], s + 1) for s in range(len(slots)))

    # Calculate number shortlists for each students
    crit = dict((n, sum(shortlists[n, c] for c in clubs)) for n in names)

    # Rescaled prefs
    prefsnew = dict()

    for n in names:
        actpref = dict((c, prefs[n, c] * shortlists[n, c]) for c in clubs if shortlists[n, c] > 0)
        scaledpref = {key: rank for rank, key in enumerate(sorted(actpref, key=actpref.get), 1)}

        for c, rank in scaledpref.items():
            prefsnew[n, c] = rank

    print('Creating IPLP')

    prob = LpProblem("ClubSelections", LpMinimize)

    choices = LpVariable.dicts("Choice", (slots, clubs, names), 0, 1, LpInteger)
    total = min(sum(shortlists.values()), sum(panels.values()))

    # Objective - allocate max students to the initial few slots
    prob += lpSum(
        [choices[s][c][n] * costs[s] * (1 - prefsnew.get((n, c), crit[n]) / (crit[n] + 1)) for s in slots for n in names
         for c in
         clubs]), "Sum_of_costs_all_students"

    # Constraint all students to be allocated
    prob += lpSum(
        [choices[s][c][n] for s in slots for n in names for c in clubs]) == total, "Sum_of_all_students"

    # Constraint - maximum number in a slot for a club is limited by panels
    for c in clubs:
        for s in slots:
            prob += lpSum([choices[s][c][n] for n in names]) <= panels[s, c], "Sum_of_students_in_slot_%s_%s" % (c, s)

    # Constraint - allocate student only if he has a shortlist
    for n in names:
        for c in clubs:
            prob += lpSum([choices[s][c][n] for s in slots]) <= shortlists[n, c], "Sum_of_slots_for_student_%s_%s" % (
                c, n)

    # Constraint - slots should not conflict for a student
    for s in slots:
        for n in names:
            prob += lpSum([choices[s][c][n] for c in clubs]) <= 1, "Sum_slots_per_student_all_clubs_%s_%s" % (s, n)

    print('Begin Solving')

    prob.solve(COINMP_DLL())

    print("Status:", LpStatus[prob.status])

    schedout = open('schedule.csv', 'w')
    line = 'Slot'

    for c in clubs:
        for j in range(int(maxpanels[c])):
            line = line + ',' + c + str(j + 1)

    schedout.write(line + '\n')
    for s in slots:
        line = s
        for c in clubs:
            row = [''] * int(maxpanels[c])
            i = 0
            for n in names:
                if choices[s][c][n].varValue == 1:
                    row[i] = n + ' ' + str(int(prefsnew[n, c])) + '_' + str(int(crit[n]))
                    i = i + 1

            line = line + ',' + ','.join(row)

        schedout.write(line + '\n')

    schedout.close()

    namesout = open('names.csv', 'w')
    line = 'Slot'

    for n in names:
        line = line + ',' + n

    namesout.write(line + '\n')
    for s in slots:
        line = s
        for n in names:
            row = ''
            for c in clubs:
                if choices[s][c][n].varValue == 1:
                    row = c + '_' + str(int(prefsnew[n, c]))

            line = line + ',' + row

        namesout.write(line + '\n')

    namesout.close()
    print(datetime.now().time())
