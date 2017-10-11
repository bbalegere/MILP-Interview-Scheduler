import getopt
from datetime import datetime

from gurobipy import *


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
                try:
                    matrix[row[0], row_header[i]] = float(row[i])
                except ValueError:
                    matrix[row[0], row_header[i]] = row[i]

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


def read_shortlists(filename):
    companies, shortlists, names = list(), dict(), set()
    with open(filename) as f:
        for csvline in f:
            csvline = csvline.strip()
            if len(companies) == 0:
                companies = csvline.split(',')
                continue

            row = csvline.split(',')
            for i in range(len(row)):
                n = row[i].strip()
                if len(n) > 1:
                    names.add(n)
                    shortlists[n, companies[i]] = 1
    return shortlists, companies, names


def usage():
    print("Usage: InterviewScheduler -s Shortlists.csv -t SlotsPanels.csv -p Prefs.csv -i SlotsInterview.csv -f ManualSched.csv")


def main(argv):
    try:
        opts, args = getopt.getopt(argv, "hp:i:f:s:t:", ["help", "prefs=", "interviewslots=", "fixed=", "shortlist=", "time="])
    except getopt.GetoptError:
        usage()
        sys.exit(2)

    shortlists = dict()
    companies = list()
    names = list()
    slots = list()
    panels = dict()
    prefs = dict()
    slots_int = dict()
    fixedints = dict()

    for opt, arg in opts:
        if opt in ("-h", "--help"):
            usage()
            sys.exit()
        elif opt in ("-s", "--shortlist"):
            shortlists, companies, names = read_shortlists(arg)
        elif opt in ("-t", "--time"):
            panels, clubs2, slots = read_input_csv(arg)
            print('Number of Clubs')
            print(len(companies))
            print('Number of Candidates')
            print(len(names))
            print('Number of Slots')
            print(len(slots))

            assert (sorted(companies) == sorted(clubs2))

            for val in shortlists.values():
                if val not in [0, 1]:
                    raise ValueError('The shortlists data can have only 0s or 1s indicating whether the student has a shortlist or not')

            for val in panels.values():
                if not val.is_integer():
                    raise ValueError('The number of panels should be a whole number')

                if val < 0:
                    raise ValueError('The number of panels cannot be negative')

        elif opt in ("-p", "--prefs"):
            prefs, clubs3, names2 = read_input_csv(arg)
            assert (sorted(companies) == sorted(clubs3))

            for val in prefs.values():
                if val not in range(1, len(companies) + 1):
                    raise ValueError('Incorrect preference ' + str(val) + '. It should be between 1 and ' + str(len(companies)))

        elif opt in ("-i", "--interviewslots"):
            slots_int = read_slots_interviews(arg)
        elif opt in ("-f", "--fixed"):
            fixedints, clubs4, slots2 = read_input_csv(arg)

    generateSchedule(companies, fixedints, names, panels, prefs, shortlists, slots, slots_int)


def generateSchedule(companies, fixedints, names, panels, prefs, shortlists, slots, slots_int):
    print(datetime.now().time())
    # Find out max number of panels
    maxpanels = dict((c, max(panels[s, c] for s in slots)) for c in companies)
    # Generate cost of slots
    costs = dict((slots[s], s + 1) for s in range(len(slots)))
    # Calculate number shortlists for each students
    crit = dict((n, sum(shortlists.get((n, c), 0) for c in companies)) for n in names)
    # Remove names who dont have any shortlists
    names = [key for key, value in crit.items() if value > 0]
    # Calculate number shortlists per company
    compshortlists = dict((c, sum(shortlists.get((n, c), 0) for n in names)) for c in companies)
    # Calculate total number of panels per company
    comppanels = dict((c, int(sum(panels[s, c] for s in slots) / slots_int.get(c, 1))) for c in companies)

    for c in companies:
        if compshortlists[c] > comppanels[c]:
            print(c + " has shortlists greater than no of panels " + str(compshortlists[c]) + " > " + str(comppanels[c]))
    fibonacii = [1, 2]
    for i in range(2, 1 + int(max(crit.values()))):
        fibonacii.append(fibonacii[i - 1] + fibonacii[i - 2])

    # Create Objective Coefficients
    prefsnew = dict()
    objcoeff = dict()
    for n in names:
        actpref = dict((c, prefs.get((n, c), 1) * shortlists.get((n, c), 0)) for c in companies if shortlists.get((n, c), 0) > 0)
        scaledpref = {key: rank for rank, key in enumerate(sorted(actpref, key=actpref.get), 1)}

        for c, rank in scaledpref.items():
            prefsnew[n, c] = rank
            for s in slots:
                if compshortlists[c] > comppanels[c]:
                    objcoeff[s, c, n] = (fibonacii[rank] / (crit[n])) * (len(slots) + 1 - costs[s])
                else:
                    objcoeff[s, c, n] = (1 - fibonacii[rank] / (crit[n] + 1)) * costs[s]

    print('Creating IPLP')
    model = Model('interviews')
    choices = model.addVars(slots, companies, names, vtype=GRB.BINARY, name='G')
    # Objective - allocate max students to the initial few slots
    model.setObjective(quicksum(choices[s, c, n] * objcoeff.get((s, c, n), 1) for s in slots for n in names for c in companies), GRB.MINIMIZE)
    # Constraint - maximum number in a slot for a club is limited by panels
    model.addConstrs((choices.sum(s, c, '*') <= panels[s, c] for s in slots for c in companies))
    # Constraint - allocate student only if he has a shortlist
    model.addConstrs((choices.sum('*', c, n) <= shortlists.get((n, c), 0) * slots_int.get(c, 1) for n in names for c in companies))
    # Constraint - slots should not conflict for a student
    model.addConstrs((choices.sum(s, '*', n) <= 1 for s in slots for n in names))
    # Constraint - allocate all students or number of interviews possible
    model.addConstrs((choices.sum('*', c, '*') == min(compshortlists[c], comppanels[c]) * slots_int.get(c, 1) for c in companies))
    # Constraint - for multiple slots per interview, same candidate should be allocated
    for c, si in slots_int.items():
        if si > 1:
            for i in range(si - 1, len(slots), si):
                for n in names:
                    for j in range(i - si + 1, i):
                        model.addConstr((choices[slots[i], c, n] - choices[slots[j], c, n]), GRB.EQUAL, 0)
    # Constraint - Fix manually given schedule
    for idx, n in fixedints.items():
        if n in names:
            model.addConstr(choices[idx[0], idx[1], n], GRB.EQUAL, 1)
    print('Optimising')
    model.optimize()
    solution = model.getAttr('X', choices)
    schedout = open('schedule.csv', 'w')
    line = 'Slot'
    for c in companies:
        for j in range(int(maxpanels[c])):
            line = line + ',' + c + str(j + 1)
    schedout.write(line + '\n')
    for s in slots:
        line = s
        for c in companies:
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
            for c in companies:
                if solution[s, c, n] == 1:
                    row = c + '_' + str(int(prefsnew[n, c]))

            line = line + ',' + row

        namesout.write(line + '\n')
    namesout.close()
    print(model.status)
    print(datetime.now().time())


if __name__ == "__main__":
    main(sys.argv[1:])
