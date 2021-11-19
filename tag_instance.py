import sys
import argparse
import datetime
import oci
import json
import os

assign_tag_namespace = ""
assign_tag_key = ""
assign_tag_value = ""
errors = 0
data = []
cmd = ""

def print_banner(cmd, tenancy):
    print_header("Running Tag Conpute")
    print("Starts at " + str(datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    print("Command Line  : " + ' '.join(x for x in sys.argv[1:]))
    if cmd.tag:
        if "defined" in cmd.action:
            print("Tag Namespace : " + assign_tag_namespace)
        print("Tag Key       : " + assign_tag_key)
        print("Tag Value     : " + assign_tag_value)
    print("Tenant Name   : " + str(tenancy.name))
    print("Tenant Id     : " + tenancy.id)
    print("Untagged      : " + ' '.join(x for x in cmd.except_instance))
    print("")

def print_header(name):
    chars = int(90)
    print("")
    print('#' * chars)
    print("#" + name.center(chars - 2, " ") + "#")
    print('#' * chars)

def get_string_dict(dic, namespace=False):
    retval = ""

    if dic is None or dic == "":
        return retval

    if namespace:
        for key, val in dic.items():
            if len(retval) > 0:
                retval += ", "
            retval += ", ".join("{}.{}={}".format(key, k, v) for k, v in val.items())
    else:
        retval = ', '.join("{}={}".format(k, v) for k, v in dic.items())
    return retval

def command_line():
    global cmd
    global assign_tag_namespace
    global assign_tag_key
    global assign_tag_value

    try:
        parser = argparse.ArgumentParser()
        parser.add_argument('-t', default="", dest='config_profile', help='Config file section to use (tenancy profile)')
        parser.add_argument('-p', default="", dest='proxy', help='Set Proxy (i.e. www-proxy-server.com:80) ')
        parser.add_argument('-cp', default="", dest='compartment', help='Filter by Compartment Name or Id')
        parser.add_argument('-rg', default="", dest='region', help='Filter by Region Name')
        parser.add_argument('-ei', default="AutoRun", nargs='+', dest='except_instance', help='Remove Instance of Markup')
        parser.add_argument('-ip', action='store_true', default=False, dest='is_instance_principals', help='Use Instance Principals for Authentication')
        parser.add_argument('-tag', default="", dest='tag', help='Tag in format - namespace.key=value or key=value')
        parser.add_argument('-action', default="", dest='action', choices=['add_defined', 'add_free', 'del_defined', 'del_free', 'list'], help='Action Type')
        parser.add_argument('-output', default="list", dest='output', choices=['list', 'json', 'summary'], help='Output type, default=summary')
        cmd = parser.parse_args()

        if not (cmd.action):
            parser.print_help()
            print("\nYou must specify action !!")
            raise SystemExit

        if (cmd.action == "add_defined" or cmd.action == "add_free" or cmd.action == "del_defined" or cmd.action == "del_free") and not cmd.tag:
            parser.print_help()
            print("\nYou must specify tag to add or delete !!")
            raise SystemExit

        if ("defined" in cmd.action):
            assign_tag_namespace = cmd.tag.split(".")[0]
            assign_tag_key = cmd.tag.split(".")[1].split("=")[0]
            assign_tag_value = cmd.tag.split("=")[1]
            if not (assign_tag_namespace or assign_tag_key or assign_tag_value):
                print("Error with tag format, must be in format - namespace.key=value")
                raise SystemExit

        if ("free" in cmd.action):
            assign_tag_key = cmd.tag.split("=")[0]
            assign_tag_value = cmd.tag.split("=")[1]
            if not (assign_tag_key or assign_tag_value):
                print("Error with tag format, must be in format - key=value")
                raise SystemExit

        return cmd

    except Exception as e:
        raise RuntimeError("Error in command_line: " + str(e.args))

def check_service_error(code):
    return ('max retries exceeded' in str(code).lower() or
            'auth' in str(code).lower() or
            'notfound' in str(code).lower() or
            code == 'Forbidden' or
            code == 'TooManyRequests' or
            code == 'IncorrectState' or
            code == 'LimitExceeded'
            )

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

def read_tag_namespaces(identity, tenancy):
    try:
        print("\nReading Tag Namespaces...")
        tagnamespaces = oci.pagination.list_call_get_all_results(
            identity.list_tag_namespaces,
            "ocid1.compartment.oc1..aaaaaaaadfrdmr7ckp2xvgj2q2hlg7gc6cmdkgfl5voaikjrwsuofzobvpoa",
            lifecycle_state='ACTIVE'
        ).data

        assign_tag_namespace_obj = None
        for tagnamespace in tagnamespaces:
            if tagnamespace.name == assign_tag_namespace:
                assign_tag_namespace_obj = tagnamespace
                print("   Found Tag Namespace '" + assign_tag_namespace + "', id = " + tagnamespace.id)
                break

        if not assign_tag_namespace_obj:
            print("Could not find tag namespace " + assign_tag_namespace)
            print("Abort.")
            raise SystemExit

        tags = oci.pagination.list_call_get_all_results(
            identity.list_tags,
            assign_tag_namespace_obj.id,
            lifecycle_state='ACTIVE'
        ).data

        tag_key_found = False
        for tag in tags:
            if tag.name == assign_tag_key:
                tag_key_found = True
                print("   Found Tag Key '" + assign_tag_key + "', id = " + tag.id)
                break

        if not tag_key_found:
            print("Could not find tag Key " + assign_tag_key)
            print("Abort.")
            raise SystemExit

    except Exception as e:
        raise RuntimeError("\nError checking tagnamespace - " + str(e))

def identity_read_compartments(identity, tenancy):

    global cmd
    print("Loading Compartments...")
    try:
        compartments = oci.pagination.list_call_get_all_results(
            identity.list_compartments,
            tenancy.id,
            compartment_id_in_subtree=True,
        ).data

        compartments.append(tenancy)

        filtered_compartment = []
        for compartment in compartments:
            if compartment.id != tenancy.id and compartment.lifecycle_state != oci.identity.models.Compartment.LIFECYCLE_STATE_ACTIVE:
                continue

            if cmd.compartment:
                if compartment.id != cmd.compartment and compartment.name != cmd.compartment:
                    continue

            filtered_compartment.append(compartment)

        print("    Total " + str(len(filtered_compartment)) + " compartments loaded.")
        return filtered_compartment

    except Exception as e:
        raise RuntimeError("Error in identity_read_compartments: " + str(e.args))

def handle_object(compartment, region_name, obj_name, list_object, update_object, update_modal_obj, availability_domains=None, namespace=""):

    global data
    global errors

    try:
        cnt = 0
        cnt_added = 0
        cnt_deleted = 0
        cnt_exist = 0

        availability_domains_array = [ad.name for ad in availability_domains] if availability_domains else ['single']

        array = []
        for availability_domain in availability_domains_array:
            try:
                if availability_domains:
                    array = oci.pagination.list_call_get_all_results(list_object, availability_domain, compartment.id, retry_strategy=oci.retry.DEFAULT_RETRY_STRATEGY).data
                elif namespace:
                    array = oci.pagination.list_call_get_all_results(list_object, namespace, compartment.id, retry_strategy=oci.retry.DEFAULT_RETRY_STRATEGY, fields=['tags']).data
                else:
                    array = oci.pagination.list_call_get_all_results(list_object, compartment.id, retry_strategy=oci.retry.DEFAULT_RETRY_STRATEGY).data
            except oci.exceptions.ServiceError as e:
                if check_service_error(e.code):
                    errors += 1
                    print("        " + obj_name + " ...errors ")
                    return
                raise
            for arr in array:
                if not namespace and obj_name != "Network CPEs":
                    if arr.lifecycle_state == "TERMINATING" or arr.lifecycle_state == "TERMINATED":
                        continue

                defined_tags, freeform_tags, tags_process = handle_tags(arr.defined_tags, arr.freeform_tags)
                obj_id = str(arr.name) if namespace else str(arr.id)

                if not arr.display_name in cmd.except_instance:
                    if tags_process == "Added" or tags_process == "Deleted":
                        if namespace:
                            update_object(namespace, obj_id, update_modal_obj(freeform_tags=freeform_tags, defined_tags=defined_tags), retry_strategy=oci.retry.DEFAULT_RETRY_STRATEGY)
                        elif obj_name == "Load Balancers":
                            update_object(update_modal_obj(freeform_tags=freeform_tags, defined_tags=defined_tags), obj_id, retry_strategy=oci.retry.DEFAULT_RETRY_STRATEGY)
                        else:
                            update_object(obj_id, update_modal_obj(freeform_tags=freeform_tags, defined_tags=defined_tags), retry_strategy=oci.retry.DEFAULT_RETRY_STRATEGY)

                value = ({
                    'region_name': region_name,
                    'compartment_name': str(compartment.name),
                    'type': obj_name,
                    'id': obj_id,
                    'display_name': str(arr.name) if namespace else str(arr.display_name),
                    'defined_tags': defined_tags,
                    'freeform_tags': freeform_tags,
                    'tags_process': tags_process
                })

                if not value['display_name'] in cmd.except_instance:
                    data.append(value)
                    cnt += 1
                    cnt_added += (1 if tags_process == "Added" else 0)
                    cnt_deleted += (1 if tags_process == "Deleted" else 0)
                    cnt_exist += (1 if tags_process == "Exist" else 0)

        if cnt == 0:
            print("        " + obj_name.ljust(22) + " - (-)")
        elif "del" in cmd.action:
            print("        " + obj_name.ljust(22) + " - " + str(cnt).ljust(5) + str(" Tag Deleted = " + str(cnt_deleted)).ljust(22) + " Tag Exist = " + str(cnt_exist))
        elif "add" in cmd.action:
            print("        " + obj_name.ljust(22) + " - " + str(cnt).ljust(5) + str(" Tag Added = " + str(cnt_added)).ljust(22) + " Tag Exist = " + str(cnt_exist))
        else:
            print("        " + obj_name.ljust(22) + " - " + str(cnt))

    except Exception as e:
        print("Error in handle_object: " + obj_name + " " + str(e.args))
        errors += 1

def handle_tags(defined_tags, freeform_tags):
    try:
        tags_process = ""

        if "defined" in cmd.action:
            defined_tags_exist = False
            if defined_tags:
                if assign_tag_namespace in defined_tags:
                    if assign_tag_key in defined_tags[assign_tag_namespace]:
                        if defined_tags[assign_tag_namespace][assign_tag_key] == assign_tag_value:
                            defined_tags_exist = True
                            tags_process = "Exist"

            if "del" in cmd.action:
                if defined_tags_exist:
                    defined_tags[assign_tag_namespace].pop(assign_tag_key, None)
                    if not defined_tags[assign_tag_namespace]:
                        defined_tags.pop(assign_tag_namespace, None)
                    tags_process = "Deleted"

            else:
                if not defined_tags_exist:
                    if not defined_tags:
                        defined_tags = {}

                    if assign_tag_namespace in defined_tags:
                        defined_tags[assign_tag_namespace][assign_tag_key] = assign_tag_value
                    else:
                        defined_tags[assign_tag_namespace] = {assign_tag_key: assign_tag_value}
                    tags_process = "Added"

        if "free" in cmd.action:
            freeform_tags_exist = False
            if freeform_tags:
                if assign_tag_key in freeform_tags:
                    if freeform_tags[assign_tag_key] == assign_tag_value:
                        freeform_tags_exist = True
                        tags_process = "Exist"

            if "del" in cmd.action:
                if freeform_tags_exist:
                    freeform_tags.pop(assign_tag_key, None)
                    tags_process = "Deleted"

            else:
                if not freeform_tags_exist:
                    if not freeform_tags:
                        freeform_tags = {}
                    freeform_tags[assign_tag_key] = assign_tag_value
                    tags_process = "Added"

        return defined_tags, freeform_tags, tags_process

    except Exception as e:
        raise RuntimeError("Error in handle_tags: " + str(e.args))

def main():
    global data
    cmd = command_line()

    config, signer = create_signer(cmd.config_profile, cmd.is_instance_principals)
    compartments = []
    tenancy = None
    try:
        print("\nConnecting to Identity Service...")
        identity = oci.identity.IdentityClient(config, signer=signer)
        if cmd.proxy:
            identity.base_client.session.proxies = {'https': cmd.proxy}

        tenancy = identity.get_tenancy(config["tenancy"]).data
        regions = identity.list_region_subscriptions(tenancy.id).data
        compartments = identity_read_compartments(identity, tenancy)

    except Exception as e:
        raise RuntimeError("\nError extracting compartments section - " + str(e))

    print_banner(cmd, tenancy)

    if "defined" in cmd.action and cmd.tag:
        read_tag_namespaces(identity, tenancy)

    print("\nProcessing Regions...")
    data = []
    errors = 0
    for region_name in [str(es.region_name) for es in regions]:

        if cmd.region:
            if cmd.region not in region_name:
                continue

        print("\nRegion " + region_name + "...")

        config['region'] = region_name
        signer.region = region_name
        compute_client = oci.core.ComputeClient(config, signer=signer)
        identity_client = oci.identity.IdentityClient(config, signer=signer)
        objectstorage_client = oci.object_storage.ObjectStorageClient(config, signer=signer)

        if cmd.proxy:
            compute_client.base_client.session.proxies = {'https': cmd.proxy}

        availability_domains = identity_client.list_availability_domains(tenancy.id).data

        namespace = objectstorage_client.get_namespace().data

        try:
            for compartment in compartments:
                print("    Compartment " + str(compartment.name))
                handle_object(compartment, region_name, "Instances", compute_client.list_instances, compute_client.update_instance, oci.core.models.UpdateInstanceDetails)
        except Exception as e:
            raise RuntimeError("\nError extracting Instances - " + str(e))

    if cmd.output == "json":
        print_header("Output as JSON")
        print(json.dumps(data, indent=4, sort_keys=False))

    if cmd.output == "list":
        print_header("Output as List")
        for item in data:
            print(
                item['region_name'].ljust(12) + " | " +
                item['compartment_name'].ljust(20) + " | " +
                item['type'].ljust(20) + " | " +
                item['display_name'].ljust(20) + " | " +
                item['tags_process'].ljust(12) + " | " +
                get_string_dict(item['freeform_tags']) + " | " +
                get_string_dict(item['defined_tags'], True)
            )

    if errors > 0:
        print_header(str(errors) + " errors appeared")
    print_header("Completed at " + str(datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")))

main()
