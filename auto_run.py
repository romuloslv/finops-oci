import oci
import datetime
import calendar
import threading
import time
import sys
import argparse
import os

RateLimitDelay = 2
LogLevel = "ALL"
AnyDay = "AnyDay"
Weekend = "Weekend"
WeekDay = "WeekDay"
AlternativeWeekend = False
ComputeShutdownMethod = "SOFTSTOP"
current_host_time = datetime.datetime.today()
current_utc_time = datetime.datetime.utcnow()

def print_header(name):
    chars = int(90)
    MakeLog("")
    MakeLog('#' * chars)
    MakeLog("#" + name.center(chars - 2, " ") + "#")
    MakeLog('#' * chars)

def get_current_hour(region, ignore_region_time=False):
    if region == 'us-ashburn-1':
        timezdiff = -4
    elif region == 'sa-saopaulo-1':
        timezdiff = -3
    elif region == 'sa-vinhedo-1':
        timezdiff = -3
    elif region == 'us-phoenix-1':
        timezdiff = -7
    else:
        timezdiff = 0

    current_time = current_host_time

    if not ignore_region_time:
        current_time = current_utc_time + datetime.timedelta(hours=timezdiff)

    iDayOfWeek = current_time.weekday()
    iDay = calendar.day_name[iDayOfWeek]
    iCurrentHour = current_time.hour
    return iDayOfWeek, iDay, iCurrentHour

def create_signer(config_profile, is_instance_principals):
    if is_instance_principals:
        try:
            signer = oci.auth.signers.InstancePrincipalsSecurityTokenSigner()
            config = {'region': signer.region, 'tenancy': signer.tenancy_id}
            return config, signer
        except Exception:
            print_header("Error obtaining instance principals certificate, aborting")
            raise SystemExit
    else:
        config = oci.config.from_file(
            oci.config.DEFAULT_LOCATION,
            (config_profile if config_profile else oci.config.DEFAULT_PROFILE)
        )
        signer = oci.signer.Signer(
            tenancy=config["tenancy"],
            user=config["user"],
            fingerprint=config["fingerprint"],
            private_key_file_location=config.get("key_file"),
            pass_phrase=oci.config.get_config_value_or_default(config, "pass_phrase"),
            private_key_content=config.get("key_content")
        )
        return config, signer

def MakeLog(msg, no_end=False):
    if no_end:
        print(msg, end="")
    else:
        print(msg)

def isWeekDay(day):
    weekday = True
    if AlternativeWeekend:
        if day == 4 or day == 5:
            weekday = False
    else:
        if day == 5 or day == 6:
            weekday = False
    return weekday

def isDeleted(state):
    deleted = False
    try:
        if state == "TERMINATED" or state == "TERMINATING":
            deleted = True
        if state == "DELETED" or state == "DELETING":
            deleted = True
    except Exception:
        deleted = True
        MakeLog("No lifecyclestate found, ignoring resource")
        MakeLog(state)
    return deleted

def identity_read_compartments(identity, tenancy):
    MakeLog("Loading Compartments...")
    try:
        cs = oci.pagination.list_call_get_all_results(
            identity.list_compartments,
            tenancy.id,
            compartment_id_in_subtree=True,
            retry_strategy=oci.retry.DEFAULT_RETRY_STRATEGY
        ).data
        tenant_compartment = oci.identity.models.Compartment()
        tenant_compartment.id = tenancy.id
        tenant_compartment.name = tenancy.name
        tenant_compartment.lifecycle_state = oci.identity.models.Compartment.LIFECYCLE_STATE_ACTIVE
        cs.append(tenant_compartment)
        MakeLog("    Total " + str(len(cs)) + " compartments loaded.")
        return cs
    except Exception as e:
        raise RuntimeError("Error in identity_read_compartments: " + str(e.args))

def autoscale_region(region):
    global total_resources
    global ErrorsFound
    global errors
    global success

    MakeLog("Starting Auto Run script on region {}, executing {} actions".format(region, Action))
    DayOfWeek, Day, CurrentHour = get_current_hour(region, cmd.ignore_region_time)

    if AlternativeWeekend:
        MakeLog("Using Alternative weekend (Friday and Saturday as weekend")
    if cmd.ignore_region_time:
        MakeLog("Ignoring Region Datetime, Using local time")

    MakeLog("Day of week: {}, IsWeekday: {},  Current hour: {}".format(Day, isWeekDay(DayOfWeek), CurrentHour))
    CurrentHour = 23 if CurrentHour == 0 else CurrentHour - 1
    MakeLog("Getting all resources supported by the search function...")
    
    query = "query all resources where (definedTags.namespace = '{}')".format(PredefinedTag)
    sdetails = oci.resource_search.models.StructuredSearchDetails()
    sdetails.query = query
    result = search.search_resources(search_details=sdetails, limit=1000, retry_strategy=oci.retry.DEFAULT_RETRY_STRATEGY).data
    total_resources += len(result.items)

    MakeLog("")
    MakeLog("Checking {} Resources for Auto Run...".format(len(result.items)))

    for resource in result.items:
        resourceOk = False
        if cmd.print_ocid:
            MakeLog("Checking {} ({}) - {}...".format(resource.display_name, resource.resource_type, resource.identifier))
        else:
            MakeLog("Checking {} ({})...".format(resource.display_name, resource.resource_type))
        
        if resource.resource_type == "Instance":
            resourceDetails = compute.get_instance(instance_id=resource.identifier, retry_strategy=oci.retry.DEFAULT_RETRY_STRATEGY).data
            resourceOk = True
        
        if not isDeleted(resource.lifecycle_state) and resourceOk:
            schedule = resourceDetails.defined_tags[PredefinedTag]
            ActiveSchedule = ""
            
            if AnyDay in schedule:
                ActiveSchedule = schedule[AnyDay]
            if isWeekDay(DayOfWeek):
                if WeekDay in schedule:
                    ActiveSchedule = schedule[WeekDay]
            else:
                if Weekend in schedule:
                    ActiveSchedule = schedule[Weekend]
            if Day in schedule:
                ActiveSchedule = schedule[Day]
            
            if ActiveSchedule != "":
                try:
                    schedulehours = ActiveSchedule.split(",")
                    if len(schedulehours) != 24:
                        ErrorsFound = True
                        errors.append(" - Error with schedule of {} - {}, not correct amount of hours, I count {}".format(resource.display_name, ActiveSchedule, len(schedulehours)))
                        MakeLog(" - Error with schedule of {} - {}, not correct amount of hours, i count {}".format(resource.display_name, ActiveSchedule, len(schedulehours)))
                        ActiveSchedule = ""
                except Exception:
                    ErrorsFound = True
                    ActiveSchedule = ""
                    errors.append(" - Error with schedule for {}".format(resource.display_name))
                    MakeLog(" - Error with schedule of {}".format(resource.display_name))
                    MakeLog(sys.exc_info()[0])
            else:
                MakeLog(" - Ignoring instance, as no active schedule for today found")
            
            if ActiveSchedule != "":
                DisplaySchedule = ""
                c = 0
                for h in schedulehours:
                    if c == CurrentHour:
                        DisplaySchedule = DisplaySchedule + "[" + h + "],"
                    else:
                        DisplaySchedule = DisplaySchedule + h + ","
                    c = c + 1

                MakeLog(" - Active schedule for {}: {}".format(resource.display_name, DisplaySchedule))
                if schedulehours[CurrentHour].replace(" ", "") == "*":
                    MakeLog(" - Ignoring this service for this hour")
                else:
                    if resource.resource_type == "Instance":
                        if int(schedulehours[CurrentHour]) == 0 or int(schedulehours[CurrentHour]) == 1:
                            if resourceDetails.shape[:2] == "VM":
                                if resourceDetails.lifecycle_state == "RUNNING" and int(schedulehours[CurrentHour]) == 0:
                                    if Action == "All" or Action == "Down":
                                        MakeLog(" - Initiate Compute VM shutdown for {}".format(resource.display_name))
                                        Retry = True
                                        while Retry:
                                            try:
                                                response = compute.instance_action(instance_id=resource.identifier, action=ComputeShutdownMethod)
                                                Retry = False
                                                success.append(" - Initiate Compute VM shutdown for {}".format(resource.display_name))
                                            except oci.exceptions.ServiceError as response:
                                                if response.status == 429:
                                                    MakeLog("Rate limit kicking in.. waiting {} seconds...".format(RateLimitDelay))
                                                    time.sleep(RateLimitDelay)
                                                else:
                                                    ErrorsFound = True
                                                    errors.append(" - Error ({}) Compute VM Shutdown for {} - {}".format(response.status, resource.display_name, response.message))
                                                    MakeLog(" - Error ({}) Compute VM Shutdown for {} - {}".format(response.status, resource.display_name, response.message))
                                                    Retry = False
                                if resourceDetails.lifecycle_state == "STOPPED" and int(schedulehours[CurrentHour]) == 1:
                                    if Action == "All" or Action == "Up":
                                        MakeLog(" - Initiate Compute VM startup for {}".format(resource.display_name))
                                        Retry = True
                                        while Retry:
                                            try:
                                                response = compute.instance_action(instance_id=resource.identifier, action="START")
                                                Retry = False
                                                success.append(" - Initiate Compute VM startup for {}".format(resource.display_name))
                                            except oci.exceptions.ServiceError as response:
                                                if response.status == 429:
                                                    MakeLog("Rate limit kicking in.. waiting {} seconds...".format(RateLimitDelay))
                                                    time.sleep(RateLimitDelay)
                                                else:
                                                    ErrorsFound = True
                                                    errors.append(" - Error ({}) Compute VM startup for {} - {}".format(response.status, resource.display_name, response.message))
                                                    Retry = False

parser = argparse.ArgumentParser()
parser.add_argument('-t', default="", dest='config_profile', help='Config file section to use (tenancy profile)')
parser.add_argument('-ip', action='store_true', default=False, dest='is_instance_principals', help='Use Instance Principals for Authentication')
parser.add_argument('-a', default="All", dest='action', help='Action All, Down, Up')
parser.add_argument('-tag', default="Periods", dest='tag', help='Tag to examine, Default=Periods')
parser.add_argument('-rg', default="", dest='filter_region', help='Filter Region')
parser.add_argument('-ignrtime', action='store_true', default=False, dest='ignore_region_time', help='Ignore Region Time - Use Host Time')
parser.add_argument('-printocid', action='store_true', default=False, dest='print_ocid', help='Print OCID for resources')
cmd = parser.parse_args()

if not (cmd.is_instance_principals):
    parser.print_help()
    print("\nYou must specify action !!")
    raise SystemExit

if cmd.action != "All" and cmd.action != "Down" and cmd.action != "Up":
    parser.print_help()
    sys.exit(0)

filter_region = cmd.filter_region
Action = cmd.action
PredefinedTag = cmd.tag
start_time = str(datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

# MAIN
print_header("Running Auto Run")
config, signer = create_signer(cmd.config_profile, cmd.is_instance_principals)
compartments = []
tenancy = None
tenancy_home_region = ""

try:
    MakeLog("\nStarts at " + str(datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    MakeLog("Connecting to Identity Service...")
    identity = oci.identity.IdentityClient(config, signer=signer)
    tenancy = identity.get_tenancy(config["tenancy"]).data
    regions = identity.list_region_subscriptions(tenancy.id).data

    for reg in regions:
        if reg.is_home_region:
            tenancy_home_region = str(reg.region_name)

    MakeLog("")
    MakeLog("Command Line  : " + ' '.join(x for x in sys.argv[1:]))
    MakeLog("Tenant Name   : " + str(tenancy.name))
    MakeLog("Tenant Id     : " + tenancy.id)
    MakeLog("Home Region   : " + tenancy_home_region)
    MakeLog("Action        : " + Action)
    MakeLog("Tag           : " + PredefinedTag)

    if cmd.filter_region:
        MakeLog("Filter Region : " + cmd.filter_region)

    MakeLog("")
    compartments = identity_read_compartments(identity, tenancy)
except Exception as e:
    raise RuntimeError("\nError connecting to Identity Service - " + str(e))

success = []
errors = []
total_resources = 0
ErrorsFound = False

for region_name in [str(es.region_name) for es in regions]:
    if cmd.filter_region:
        if cmd.filter_region not in region_name:
            continue

    print_header("Region " + region_name)
    config['region'] = region_name
    signer.region = region_name
    compute = oci.core.ComputeClient(config, signer=signer)
    search = oci.resource_search.ResourceSearchClient(config, signer=signer)
    autoscale_region(region_name)
