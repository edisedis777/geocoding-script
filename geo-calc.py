# ----------------------------- CONFIGURATION -----------------------------#

# Set the input and output files
input_file_path = "TEST_ADDR_IN.csv"
output_dir = "output_test_coord"
output_file_path = output_dir + "/geocoded_output"  # appends "####.csv" to the file name when it writes the file.

if not os.path.isdir(output_dir):
    print("Created the output directory \"{}\" since it did not exist.".format(output_dir))
    os.mkdir(output_dir)

# Set the name of the column indexes here so that pandas can read the CSV file
address_column_name = "ADDRESS"
city_column_name = "CITY"
plz_column_name = "PLZ"   # Leave blank("") if you do not have plz codes

# Where the program starts processing the addresses in the input file
# This is useful in case the computer crashes so you can resume the program where it left off or so you can run multiple
# instances of the program starting at different spots in the input file
start_index = 0
# How often the program prints the status of the running program
status_rate = 100
# How often the program saves a backup file
write_data_rate = 500
# How many times the program tries to geocode an address before it gives up
attempts_to_geocode = 3
# Time it delays each time it does not find an address
# Note that this is added to itself each time it fails so it should not be set to a large number
wait_time = 3

# ----------------------------- Processing the input file -----------------------------#

df = pd.read_csv(input_file_path, low_memory=False)
# df = pd.read_excel(input_file_path)

# Raise errors if the provided column names could not be found in the input file
if address_column_name not in df.columns:
    raise ValueError("Can't find the address column in the input file.")
if city_column_name not in df.columns:
    raise ValueError("Can't find the state column in the input file.")

# plz code is not needed but helps provide more accurate locations
if plz_column_name:
    if plz_column_name not in df.columns:
        raise ValueError("Can't find the plz code column in the input file.")
    addresses = (df[address_column_name] + ', ' + df[plz_column_name].astype(str) + ', ' + df[city_column_name]).tolist()
else:
    addresses = (df[address_column_name] + ', ' + df[city_column_name]).tolist()


# ----------------------------- Function Definitions -----------------------------#

# Creates request sessions for geocoding
class GeoSessions:
    def __init__(self):
        self.Arcgis = requests.Session()
        self.Komoot = requests.Session()


# Class that is used to return 3 new sessions for each geocoding source
def create_sessions():
    return GeoSessions()


# Main geocoding function that uses the geocoding package to covert addresses into lat, longs
def geocode_address(address, s):
    g = geocoder.arcgis(address, session=s.Arcgis)
    if not g.ok:
        g = geocoder.komoot(address, session=s.Komoot)

    return g


def try_address(address, s, attempts_remaining, wait_time):
    g = geocode_address(address, s)
    if not g.ok:
        time.sleep(wait_time)
        s = create_sessions()  # It is not very likely that we can't find an address so we create new sessions and wait
        if attempts_remaining > 0:
            try_address(address, s, attempts_remaining-1, wait_time+wait_time)
    return g


# Function used to write data to the output file
def write_data(data, index):
    file_name = (output_file_path + str(index))
    print("Created the file: " + file_name)
    done = pd.DataFrame(data)
    done.columns = ['Address', 'Lat', 'Long', 'Provider']
    done.to_csv((file_name + ".csv"), sep=',', encoding='utf8', index=False)


# Variables used in the main for loop that do not need to be modified by the user
s = create_sessions()
results = []
failed = 0
total_failed = 0
progress = len(addresses) - start_index

# ----------------------------- Main Loop -----------------------------#

for i, address in enumerate(addresses[start_index:]):
    # Print the status of how many addresses have be processed so far and how many of the failed.
    if (start_index + i) % status_rate == 0:
        total_failed += failed
        print("Completed {} of {}. Failed {} for this section and {} in total."
              .format(i + start_index, progress, failed, total_failed))
        failed = 0

    # Try geocoding the addresses
    try:
        g = try_address(address, s, attempts_to_geocode, wait_time)
        if not g.ok:
            results.append([address, "was", "not", "geocoded"])
            print("Gave up on address: " + address)
            failed += 1
        else:
            results.append([address, g.latlng[0], g.latlng[1], g.provider])

    # If we failed with an error like a timeout we will try the address again after we wait 5 secs
    except Exception as e:
        print("Failed with error {} on address {}. Will try again.".format(e, address))
        try:
            time.sleep(5)
            s = create_sessions()
            g = geocode_address(address, s)
            if not g.ok:
                print("Did not fine it.")
                results.append([address, "was", "not", "geocoded"])
                failed += 1
            else:
                print("Successfully found it.")
                results.append([address, g.latlng[0], g.latlng[1], g.provider])
        except Exception as e:
            print("Failed with error {} on address {} again.".format(e, address))
            failed += 1
            results.append([address, e, e, "ERROR"])

    # Writing what has been processed so far to an output file
    if i % write_data_rate == 0 and i != 0:
        write_data(results, i + start_index)
        print(i, g.latlng, g.provider)


# Finished
write_data(results, "_done")
print("Finished! :)")