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
            for i in xrange(1, len(row)):
                matrix[row[0], row_header[i]] = float(row[i])

    row_header.pop(0)
    col_header = sorted(col_header)
    return matrix, row_header, col_header


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print >> sys.stderr, "Usage: InterviewScheduler Shortlists.csv SlotsPanels.csv Prefs.csv"
        exit(-1)
    shortlists, clubs, names = read_input_csv(sys.argv[1])
    print(datetime.now().time())
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

    # Find out max number of panels
    maxpanels = dict((c, max(panels[s, c] for s in slots)) for c in clubs)

    # Generate cost of slots
    costs = dict((slots[s], s + 1) for s in xrange(len(slots)))

    # Calculate number shortlists for each students
    crit = dict((n, sum(shortlists[n, c] for c in clubs)) for n in names)

    # Rescaled prefs
    prefsnew = dict()

    for n in names:
        actpref = dict((c, prefs[n, c] * shortlists[n, c]) for c in clubs if shortlists[n, c] > 0)
        scaledpref = {key: rank for rank, key in enumerate(sorted(actpref, key=actpref.get), 1)}

        for c, rank in scaledpref.iteritems():
            prefsnew[n, c] = rank

    print('Creating IPLP')

    model = Model('interviews')
    vars = model.addVars(slots, clubs, names, vtype=GRB.BINARY, name='G')

    # Objective - allocate max students to the initial few slots
    model.setObjective(
        quicksum(
            vars[s, c, n] * costs[s] * (totalClubs - prefsnew.get((n, c), totalClubs))
            for s in slots for n in names for c in clubs),
        GRB.MINIMIZE)

    totalstudents = sum(shortlists.values())

    # Constraint all students to be allocated
    model.addConstr((vars.sum() == totalstudents))

    # Constraint - maximum number in a slot for a club is limited by panels
    model.addConstrs((vars.sum(s, c, '*') <= panels[s, c] for s in slots for c in clubs))

    # Constraint - allocate student only if he has a shortlist
    model.addConstrs((vars.sum('*', c, n) <= shortlists[n, c] for n in names for c in clubs))

    # Constraint - slots should not conflict for a student
    model.addConstrs((vars.sum(s, '*', n) <= 1 for s in slots for n in names))

    print('Optimising')
    model.optimize()

    solution = model.getAttr('X', vars)

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
                if solution[s, c, n] == 1:
                    l[i] = n + ' ' + str(int(prefsnew[n, c])) + '_' + str(int(crit[n]))
                    i = i + 1

            line = line + ',' + ','.join(l)

        schedout.write(line + '\n')

    schedout.close()

    print(model.status)
    print(datetime.now().time())
