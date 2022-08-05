# Manage resources in pre-programmed periods based in tags

## Supported services

* Compute VMs: On/Off  
* Database VMs: On/Off
* Load Balancer: Scaling Between(10 and 8000 Mbps)

## Variables GitLab - Schedule

* KEYVALUE    = Periods.WeekDay=*, *, *, *, *, *, *, 1, *, *, *, *, *, *, *, *, *, *, *, *, *, 0, *, *-Periods.Weekend=*, *, *, *, *, *, *, *, *, *, *, *, *, *, *, *, *, *, *, *, *, *, *, *
* SERVICES    = compute,database,loadbalancer
* ACTION      = Up or Down
* NAMESPACE   = Periods
* COMPARTMENT = XXXXXX
* PROFILE     = XXXXXX
* REGION      = XXXXXX
* SIZE        = XXXXXX
* TIME        = XXXXXX
* UNTAGGED    = XXXXXX

## Variables GitLab

OCI_CONFIG_PROFILE = XXXXXX  
OCI_KEY_PEM        = XXXXXX

## Usage

```
[opc@autorun scripts]$ python3 auto_run.py
usage: auto_run.py [-h] [-t CONFIG_PROFILE] [-ip] [-cp COMPARTMENT] [-a ACTION] [-di DELAY] [-sl SIZE]
                   [-tag TAG] [-rg FILTER_REGION] [-ignrtime] [-printocid]

optional arguments:
  -h, --help         Show this help message and exit
  -t CONFIG_PROFILE  Config file section to use (tenancy profile)
  -ip                Use Instance Principals for Authentication
  -cp COMPARTMENT    Filter by Compartment Name or Id
  -a ACTION          Action All, Down, Up
  -di DELAY          Instance launch delay in seconds
  -sl SIZE           Load Balancer size in MBs
  -tag TAG           Tag to examine, Default=Periods
  -rg FILTER_REGION  Filter Region
  -ignrtime          Ignore Region Time - Use Host Time
  -printocid         Print OCID for resources

You must specify action !!

[opc@autorun scripts]$ python3 mark_tag_instance.py
usage: mark_tag_instance.py [-h] [-t CONFIG_PROFILE] [-p PROXY] [-cp COMPARTMENT] [-rg REGION] [-ip] [-dt]
                            [-tag TAG] [-utag EXCEPT_INSTANCE [EXCEPT_INSTANCE ...]] [-tagseperator TAGSEPERATOR]
                            [-action {add_defined,add_free,del_defined,del_free,list}] [-output {list,json,summary}]
                            [-force] [-service SERVICE] [-filter_by_name FILTER_BY_NAME]

optional arguments:
  -h, --help                                   Show this help message and exit
  -t CONFIG_PROFILE                            Config file section to use (tenancy profile)
  -p PROXY                                     Set Proxy (i.e. www-proxy-server.com:80)
  -cp COMPARTMENT                              Filter by Compartment Name or Id
  -rg REGION                                   Filter by Region Name
  -ip                                          Use Instance Principals for Authentication
  -dt                                          Use Delegation Token for Authentication
  -tag TAG                                     Tags in format - namespace.key=value or key=value
                                               with comma seperator for multi tags
  -utag EXCEPT_INSTANCE [EXCEPT_INSTANCE ...]  Remove Instance of Markup
  -tagseperator TAGSEPERATOR                   Tag Seperator for multiple tags, default=,
  -action {add_defined,del_defined,list}       Action Type
  -output {list,json,summary}                  Output type, default=summary
  -force                                       Force execution (do not confirm)
  -service SERVICE                             Services = all,compute,block,network,identity... default=all
  -filter_by_name FILTER_BY_NAME               Filter service by name comma seperator for multi

You must specify action !!
```

## TL;DR

### "x, ..., y" = daily hours tags

|    Value    | Description |
|    :----:   |    :----:   |
| "0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0" | turn on every hour |
| "1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1" | turn off every hour |
| "*, *, *, *, *, *, *, 1, *, *, *, *, *, *, *, *, *, *, 0, *, *, *, *, *" | turn on at 8 am and turn off at 8 pm |
| "*, *, *, *, *, *, *, *, *, *, *, *, *, *, *, *, *, *, *, *, *, *, *, *" | respect the current status |
