from gurobipy import *
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


def read_slots_interviews(filename):
    row_header = list()
    slots_c = list()
    with open(filename) as f:
        for csvline in f:
            csvline = csvline.strip()
            if len(row_header) == 0:
                row_header = csvline.split(',')
                continue

            slots_c = map(int, csvline.split(','))

    return dict(zip(row_header, slots_c))


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

    for val in shortlists.values():
        if val not in [0, 1]:
            raise ValueError('The shortlists data can have only 0s or 1s indicating whether the student has a shortlist or not')

    for val in panels.values():
        if not val.is_integer():
            raise ValueError('The number of panels should be a whole number')

        if val < 0:
            raise ValueError('THe number of panels cannot be negative')

    slots_int = dict()
    if len(sys.argv) > 4:
        slots_int = read_slots_interviews(sys.argv[4])

    # Find out max number of panels
    maxpanels = dict((c, max(panels[s, c] for s in slots)) for c in clubs)

    # Generate cost of slots
    costs = dict((slots[s], s + 1) for s in range(len(slots)))

    # Calculate number shortlists for each students
    crit = dict((n, sum(shortlists[n, c] for c in clubs)) for n in names)

    # Remove names who dont have any shortlists
    names = [key for key, value in crit.items() if value > 0]

    # Calculate number shortlists per company
    compshortlists = dict((c, sum(shortlists[n, c] for n in names)) for c in clubs)

    # Calculate total number of panels per company
    comppanels = dict((c, int(sum(panels[s, c] for s in slots) / slots_int.get(c, 1))) for c in clubs)

    for c in clubs:
        if compshortlists[c] > comppanels[c]:
            print(c + " has shortlists greater than no of panels " + str(compshortlists[c]) + " > " + str(comppanels[c]))

    # Create Objective Coefficients
    prefsnew = dict()
    objcoeff = dict()
    for n in names:
        actpref = dict((c, prefs[n, c] * shortlists[n, c]) for c in clubs if shortlists[n, c] > 0)
        scaledpref = {key: rank for rank, key in enumerate(sorted(actpref, key=actpref.get), 1)}

        for c, rank in scaledpref.items():
            prefsnew[n, c] = rank
            for s in slots:
                if compshortlists[c] > comppanels[c]:
                    objcoeff[s, c, n] = (rank / (crit[n])) * (len(slots) + 1 - costs[s])
                else:
                    objcoeff[s, c, n] = (1 - rank / (crit[n] + 1)) * costs[s]

    print('Creating IPLP')

    model = Model('interviews')
    choices = model.addVars(slots, clubs, names, vtype=GRB.BINARY, name='G')

    # Objective - allocate max students to the initial few slots
    model.setObjective(quicksum(choices[s, c, n] * objcoeff.get((s, c, n), 1) for s in slots for n in names for c in clubs), GRB.MINIMIZE)

    # Constraint - maximum number in a slot for a club is limited by panels
    model.addConstrs((choices.sum(s, c, '*') <= panels[s, c] for s in slots for c in clubs))

    # Constraint - allocate student only if he has a shortlist
    model.addConstrs((choices.sum('*', c, n) <= shortlists[n, c] * slots_int.get(c, 1) for n in names for c in clubs))

    # Constraint - slots should not conflict for a student
    model.addConstrs((choices.sum(s, '*', n) <= 1 for s in slots for n in names))

    # Constraint - allocate all students or number of interviews possible
    model.addConstrs((choices.sum('*', c, '*') == min(compshortlists[c], comppanels[c]) * slots_int.get(c, 1) for c in clubs))

    # Constraint - for multiple slots per interview, same candidate should be allocated
    for c, si in slots_int.items():
        if si > 1:
            for i in range(si - 1, len(slots), si):
                for n in names:
                    for j in range(i - si + 1, i):
                        model.addConstr((choices[slots[i], c, n] - choices[slots[j], c, n]), GRB.EQUAL, 0)

    print('Optimising')
    model.optimize()

    solution = model.getAttr('X', choices)

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
                if solution[s, c, n] == 1:
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
                if solution[s, c, n] == 1:
                    row = c + '_' + str(int(prefsnew[n, c]))

            line = line + ',' + row

        namesout.write(line + '\n')

    namesout.close()

    print(model.status)
    print(datetime.now().time())
