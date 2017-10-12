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
    return shortlists, companies, sorted(names)


def read_gdPanels(filename):
    gdcomps = set()
    with open(filename) as f:
        for csvline in f:
            csvline = csvline.strip()
            row = csvline.split(',')
            val = [x for x in row if x]
            gdcomps.add(tuple(val))

    return gdcomps


def usage():
    print("Usage: InterviewScheduler -s Shortlists.csv -t SlotsPanels.csv -p Prefs.csv -i SlotsInterview.csv -f ManualSched.csv")


def main(argv):
    try:
        opts, args = getopt.getopt(argv, "hi:f:s:t:g:", ["help", "interviewslots=", "fixed=", "shortlist=", "time=", "gdpanels="])
    except getopt.GetoptError:
        usage()
        sys.exit(2)

    shortlists = dict()
    companies = list()
    names = list()
    slots = list()
    panels = dict()
    slots_int = dict()
    fixedints = dict()
    gdpanels = list()
    for opt, arg in opts:
        if opt in ("-h", "--help"):
            usage()
            sys.exit()
        elif opt in ("-s", "--shortlist"):
            shortlists, companies, names = read_shortlists(arg)
        elif opt in ("-t", "--time"):
            panels, comp2, slots = read_input_csv(arg)
            print('Number of Companies')
            print(len(companies))
            print('Number of Candidates')
            print(len(names))
            print('Number of Slots')
            print(len(slots))

            assert (sorted(companies) == sorted(comp2))

            for val in shortlists.values():
                if val not in [0, 1]:
                    raise ValueError('The shortlists data can have only 0s or 1s indicating whether the student has a shortlist or not')

            for val in panels.values():
                if not val.is_integer():
                    raise ValueError('The number of panels should be a whole number')

                if val < 0:
                    raise ValueError('The number of panels cannot be negative')

        elif opt in ("-i", "--interviewslots"):
            slots_int = read_slots_interviews(arg)
            assert (sorted(slots_int.keys()) == sorted(companies))
        elif opt in ("-f", "--fixed"):
            fixedints, clubs4, slots2 = read_input_csv(arg)
        elif opt in ("-g", "--gdpanels"):
            gdpanels = read_gdPanels(arg)
            gdcomps = [y for x in gdpanels for y in x]
            assert (sorted(companies) == sorted(gdcomps))

    generateSchedule(companies, fixedints, names, panels, shortlists, slots, slots_int, gdpanels)


def generateSchedule(companies, fixedints, names, panels, shortlists, slots, slots_int, gdpanels):
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

    print('Creating IPLP')
    model = Model('interviews')
    choices = model.addVars(slots, companies, names, vtype=GRB.BINARY, name='G')
    # Objective - allocate max students to the initial few slots
    model.setObjective(quicksum(choices[s, c, n] * costs[s] for s in slots for n in names for c in companies), GRB.MINIMIZE)
    # Constraint - maximum number in a slot for a club is limited by panels
    model.addConstrs((choices.sum(s, c, '*') <= panels[s, c] for s in slots for c in companies))
    # Constraint - allocate student only if he has a shortlist
    model.addConstrs((choices.sum('*', c, n) <= shortlists.get((n, c[0]), 0) * slots_int.get(c[0], 1) for n in names for c in gdpanels))
    # Constraint - slots should not conflict for a student
    model.addConstrs((choices.sum(s, '*', n) <= 1 for s in slots for n in names))
    # Constraint - allocate all students or number of interviews possible
    model.addConstrs((choices.sum('*', c, '*') == min(compshortlists[c[0]], comppanels[c[0]]) * slots_int.get(c[0], 1) for c in gdpanels))
    # Constraint - for multiple slots per interview, same candidate should be allocated
    for c, si in slots_int.items():

        start_slot = 0
        while panels[slots[start_slot], c] == 0:
            start_slot += 1

        if si > 1:
            for i in range(si - 1 + start_slot, len(slots), si):
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
                    row[i] = n
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
                    row = c

            line = line + ',' + row

        namesout.write(line + '\n')
    namesout.close()
    print(model.status)
    print(datetime.now().time())


if __name__ == "__main__":
    main(sys.argv[1:])
