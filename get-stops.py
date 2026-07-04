from py12306 import get_train_stops

train = get_train_stops(train="G1", date="2026-07-05")

for stop in train.stops:
    print(stop.station, stop.arrive, stop.depart)
