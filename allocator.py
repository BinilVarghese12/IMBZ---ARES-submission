'''By default returns a list of objects with the properties (location:string, coordinates:(float,float), weight:0, allocation:int)

If given the option "csv_flag=True" then it will return True and generate a csv file called "station_allocations.csv"
'''

def get_allocations(csv_flag:bool = False):
    import csv, json,re,math;
    
    path_output = "output_data.txt";
    path_town = "towndata.csv";
    path_stations = "ambulancestations.csv";
    path_settings = "settings.json";
    
    settings = {};
    towns_raw = []
    towns = [];
    depots = [];
    
    unitweight = 0;
    
    class location:
        location = "";
        coordinates = (0,0);
        weight = 0;b
        allocation = 0;
        id = 0;
        
        def __init__(self, l, c, w, a):
            self.location = l;
            self.weight = w;
            self.allocation = a;
            self.coordinates = c;
    
    def dist(lat1, lon1, lat2, lon2):
        mean_lat = math.radians((lat1 + lat2) / 2);
        dx = math.radians(lon2 - lon1) * math.cos(mean_lat);
        dy = math.radians(lat2 - lat1);
        return 6371.0088 * math.hypot(dx, dy);
    
    with open(path_settings) as raw:
       settings = json.loads(raw.read());
    
    
    with open(path_town, newline="") as raw:
        reader = csv.reader(raw, delimiter=",");
        towns_raw = list(reader);
    
    towns_raw = towns_raw[1:];
    
    with open(path_output) as raw:
        reader = csv.reader(raw);
        for row in reader:
            if (row[0] == "town"): continue;
            r = re.split('[^0-9.]+', "".join(row))[1:3];
            ind = int(r[0])-1;
            towns.append(
                location(towns_raw[ind][0],
                         (float(towns_raw[ind][2]),float(towns_raw[ind][3])),
                         float(r[1]),0) 
            );
    
    with open(path_stations, newline="") as raw:
        reader = csv.reader(raw);
        for row in reader:
            if (row[0] == "town"): continue;
            depots.append(location(
                row[0],
                (float(row[2]),float(row[3])),
                0,
                0
            ));
    
    total = 0;
    for i in towns:
        total += i.weight;
    unitweight = 1/total;
    for i in towns:
        i.allocation = settings["ambulances"] * i.weight * unitweight;
    
        depots.sort(key=lambda a: dist(*i.coordinates, *a.coordinates));
    
        closest_dist = [];
        total = 0;
        for j in range(0,3):
            closest_dist.append(dist(*i.coordinates, *depots[j].coordinates));
        for j in range(0,3):
            total += 1/closest_dist[j];
        for j in range(0,3):
            depots[j].allocation += (1/closest_dist[j])/total * i.allocation;
    
    total = 0;
    depots.sort(key=lambda a: a.location);
    for i in depots:
        i.allocation = round(i.allocation);
        total += i.allocation;
    if not csv_flag:
        return depots;
    
    with open("station_allocations.csv", "w", newline="") as raw:
        writer = csv.writer(raw, delimiter=",");
        writer.writerow(["station", "latitude", "longitude", "allocated ambulances"]);
        for i in depots:
            writer.writerow([i.location, *i.coordinates, i.allocation]);

    return True;

if __name__ == "__main__":
    print(list(map(lambda a: [a.location, a.allocation], get_allocations())));