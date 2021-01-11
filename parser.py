import logging
from logging.config import dictConfig

logging_config = dictConfig( dict(
    version = 1,
    formatters = {
        'f': {'format':
              '%(asctime)s %(name)s %(levelname)s %(message)s'}
        },
    handlers = {
        'h': {'class': 'logging.StreamHandler',
              'formatter': 'f',
              'level': logging.DEBUG}
        },
    root = {
        'handlers': ['h'],
        'level': logging.WARNING,
        },
) )

logger = logging.getLogger()

def parse_input(filecontents:str):
    """ 
    this takes the text output for multiple gateways of `vsx stat -v && cphaprob stat && cphaprob -a if` and turns it into something useful 

    returns gateways:dict, vlans:dict, physinterfaces:dict
    
    """
    
    # initialise variables
    gateways, physinterfaces, vlans = {}, {}, {}
    current_gateway = False
    current_vsid = False
    current_interface_type = None
    full_vsid = None
    # this sets the parser mode, used for checking if you're parsing the vsid map
    linemode = "normal"

    for line in filecontents.split("\n"):
        line = line.strip()
        if line.startswith("-") or line.strip() == "" or line.startswith("=") or line.startswith("ID"):
            # skip blank/useless lines
            continue

        if line.strip() == "Virtual Devices Status":
            # start of the map of vsid
            logger.debug("Starting VSIDMap")
            linemode = "vsidmap"
        elif line.startswith("Type:") and linemode=="vsidmap":
            # stop parsing the vsid map
            linemode = "normal"
            logger.debug("Ending VSIDMap")
        elif linemode=="vsidmap" and line.startswith("ID ") == False:
            # this is part of the vsid grid 
            id, typename, policy, installed_time, sicstatus = line.split("|")
            id,typename,policy,installed_time,sicstatus = int(id.strip()),typename.strip(),policy.strip(),installed_time.strip(),sicstatus.strip()
            logger.debug((id,typename,policy,installed_time,sicstatus))
            try:
                fwtype, name = typename.strip().split()
            except ValueError:
                logger.debug("'{}'".format(typename))
                import sys
                sys.exit("Couldn't process")

            if id not in gateways[current_gateway]:
                gateways[current_gateway][id] = { 'type' : fwtype, 'name' : name, 'policy' : policy, 'installed_time' : installed_time, 'sicstatus' : sicstatus, 'is_virtualswitch' : False }
            else:
                raise ValueError("VSID {} already exists in gatway {} while processing vsidmap".format(id, current_gateway))

        elif linemode == "normal":
            if line.startswith("Name:"):
                current_gateway = line.split()[-1]
                if current_gateway not in gateways:
                    gateways[current_gateway] = {}
                    current_vsid = None
                logger.debug("[Gateway]: {}".format(current_gateway))
            elif line.strip() == "VS is working as a Virtual Switch.":
                gateways[current_gateway][current_vsid]['is_virtualswitch'] = True
                logger.debug("[virtswitch] True")
            elif line.startswith("Number of Virtual Systems allowed by license"):
                #TODO  Number of Virtual Systems allowed by license:          \d+
                pass
            # gateway-specific lines
            # Number of Virtual Systems allowed by license:          \d+
                # can't just match on Number, need more'

            elif line.startswith("Virtual Systems [active / configured]:"):
                #TODO: Virtual Systems [active / configured]:                 \d+ / \d+
                pass   
            #Virtual Routers and Switches [active / configured]:     \d+ / \d+    
            #Total connections [current / limit]:                \d+ / \d+

            # have found a new vsid
            elif line.startswith('vsid'):
                current_vsid = int(line.strip().split()[-1][:-1])
                if current_vsid not in gateways[current_gateway]:
                    # build the default object
                    gateways[current_gateway][current_vsid] = { 'is_virtualswitch' : False }
                logger.debug("[New vsid]: {}".format(current_vsid))
                # handy for identifying interfaces etc
                full_vsid = "{}+{}".format(current_gateway, current_vsid)
                continue
            
            elif line.startswith("Required interfaces"):
                current_interface_type = "physical"
                gateways[current_gateway][current_vsid]['required_interfaces'] = line.split()[-1]
                logger.debug("[physintreq]: {}".format(line.split()[-1]))
            
            elif line.startswith("Required secured interfaces"):
                gateways[current_gateway][current_vsid]['required_secure_interfaces'] = line.split()[-1]
                logger.debug("[physintsec]: {}".format(line.split()[-1]))
    
            elif line.startswith("Virtual cluster interfaces"):
                # vsid stat
                current_interface_type = "virtual"
                logger.debug("[interface_type] {}".format(current_interface_type))
                gateways[current_gateway][current_vsid]['virtual_cluster_interfaces'] = line.split()[-1]
                logger.debug("[virtclusterinterfaces] {} - virtual cluster interfaces - {}".format(current_vsid, gateways[current_gateway][current_vsid]['virtual_cluster_interfaces']))

            elif line.startswith("eth") or line.startswith("bond") or line.startswith("Sync") or line.startswith("wrp"):
                # interfaces
                try:
                    interface, ip, *details = line.split()
                    details = " ".join(details).strip()
                except ValueError:
                    interface, ip = line.split()
                    details = ""
                if '{}_interfaces'.format(current_interface_type) not in gateways[current_gateway][current_vsid].keys():
                    gateways[current_gateway][current_vsid]['{}_interfaces'.format(current_interface_type)] = {}
                gateways[current_gateway][current_vsid]['{}_interfaces'.format(current_interface_type)][interface] = (ip,details)

                # add to the global list of physical interfaces
                if current_interface_type == 'physical':
                    intid = "{}-{}".format( current_gateway, interface )
                    if intid not in physinterfaces:
                        physinterfaces[intid] = []
                    physinterfaces[intid].append(full_vsid)
                
                # add to the global list of vlans
                elif current_interface_type == 'virtual':
                    if interface.startswith('wrp'):
                        # TODO: Fix this
                        pass
                    elif (interface.startswith('eth') or interface.startswith('bond')) and "." in interface:
                        vlan = interface.split('.')[-1]
                        if vlan not in vlans:
                            vlans[vlan] = []
                        vlans[vlan].append(full_vsid)
                        logger.debug("[vlan]: {} added to vsid: {}".format(vlan, full_vsid))
                # debugging string to report a parsed interface
                logger.debug("[int]: {} {} {} {}".format('{}'.format(current_interface_type), interface, ip, details)) 
        else:
            logger.debug("[unproc]: {}".format(line.strip()))
    return gateways, vlans, physinterfaces
