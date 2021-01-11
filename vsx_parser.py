#!/usr/bin/python3                                                                                                                                                                                   

""" takes the output of the following command from checkpoint VSX clusters and puts it all together and tries to make sense of it:

command: vsx stat -v && cphaprob stat && cphaprob -a if

put the output in files in the "input_dir" folder and it'll parse them.

"""

# CONFIGURATION
input_dir = './input_files/'  
DOHTML = True
DOGRAPHS = True # if set to False, won't output the smaller graphs
DO_BIG_GRAPH = False # if set to false, won't output the full graph at the bottom
# IMPORTS
import os

from parser import parse_input

# type codes turned to text
TYPETABLE = {
    'S' : 'Virtual System', 
    'B' : 'Virtual System in Bridge mode',
    'R' : 'Virtual Router',
    'W' : 'Virtual Switch',
    'Root' : 'Root VSID',
}

def output_html(*text):
    """ output when html is asked for """
    if DOHTML:
        print(*text)

def get_vsids_by_name(vsname):
    """ returns the gateway ID and vsid by its name """
    for gateway in gateways:
        for vs in gateways[gateway]:
            name = gateways[gateway][vs].get('name', False)
            if name and name.endswith( vsname ):
                return gateways[gateway][vs]

def get_vsname_by_id(full_vsid):
    gateway, vsid = full_vsid.split("+")
    vsid = int(vsid)
    try:
        if vsid == 0:
            return 'Root'
        return gateways[gateway][vsid].get('name', 'Root')
    except KeyError:
        exit(full_vsid)

def link_to_vs_by_id(full_vsid):
    return "<a href='#{}'>{}</a>".format(full_vsid, get_vsname_by_id(full_vsid))

filecontents = ""
for filename in [ filename for filename in os.listdir(input_dir) if 'stats' in filename.lower() ]:
    with open('{}{}'.format(input_dir, filename), 'r') as fh:
        filecontents += fh.read()


gateways, vlans, physinterfaces = parse_input(filecontents)


###################################
# OUTPUT SECTION
###################################

# output the file header - only includes some clean-up CSS currently
with open('templates/header.html', 'r') as fh:
    output_html(fh.read())

# create the table of contents
output_html("<table><tr>")
# for each appliance, make a box
for gateway in sorted(gateways.keys()):
    curr_gateway = gateways[gateway]
    output_html("<td valign='top'><h1><a href='#{0}'>{0}</a></h1>".format(gateway))
    if len(curr_gateway.keys()) > 0:
        # and show a list of VS'
        output_html('<ul>')
        # sort them alphabetically by name, not by vsid
        for vsid in sorted(curr_gateway.keys(), key=lambda x: gateways[gateway][x].get('name', 'unnamed').lower()):
            name = curr_gateway[vsid].get('name', 'unnamed').replace('{}_VS_'.format(gateway),'').replace('{}_VSW_'.format(gateway),'')
            output_html("<li><a href='#{}+{}'>{}</a> ({})</li>".format(gateway, vsid, name,TYPETABLE[curr_gateway[vsid].get('type','Root')]))
        output_html('</ul>')
    output_html("</td>")
output_html("</tr></table>")

# the big list
for gatewaytocheck in sorted(gateways.keys()):
    gateway = gateways[gatewaytocheck]
    #gateway name
    output_html("<h1><a name='{0}' />{0}</h1>".format(gatewaytocheck))
    
    # grab a list of physical interfaces and vlans, so we can make an association list
    for vsid in gateway:
        vs = gateways[gatewaytocheck][vsid]
        vsname = vs.get('name', 'Root VSID')
        vsname = vsname.replace('{}_VS_'.format(gatewaytocheck),'')
        full_vsid = '{}+{}'.format(gatewaytocheck, vsid)
        # look at common vlans across VS'en
        # show the vs name, and make an anchor for it
        output_html("<h2><a name='{3}' />{0} #{1} - {2}</a></h2>".format(gatewaytocheck, vsid, vsname, full_vsid))

        if 'name' in vs:
            output_html("<table border='0' cellspacing='0' cellpadding='3'>")
            # if it's a firewall and not just a switch/router
            lastupdate = vs.get('installed_time', "")
            if lastupdate != "":
                output_html( "<tr><th>Last policy install</th><td>{}</td></tr>".format(lastupdate))
            # only show elements with policies
            if vs.get('policy', False) and vs['policy'] != "<Not Applicable>":
                output_html("<tr><th>Policy name</th><td>{}</td>".format(vs['policy']))
            # if it's not trusted, show the user
            if vs['sicstatus'] != 'Trust':
                output_html("<tr><td>SIC Status</td><td>{}</td></tr>".format(vs['sicstatus']))
            # if it's a virtualswitch, show that
            if vs['is_virtualswitch']:
                output_html("<tr><td colspan='2'>This VS is acting as a Virtual Switch</td></tr>")
            output_html("</table>")
            
            # print the physical interfaces
            if 'physical_interfaces' in vs.keys():
                # count secure interfaces               
                numsecrequired = int(vs.get('required_secure_interfaces', 0))
                output_html("<h4>{} Physical interfaces ({} secure required)</h4>".format(vs['required_interfaces'], numsecrequired))
                
                numsec = 0
                physlist = "<table>\n<tr><th>Interface</th><th>Status</th><th>Details</th></tr>\n" 
                for interface in sorted(vs['physical_interfaces']):
                    physlist += "<tr><td>{}</td><td style='text-align:center'>{}</td><td>{}</td></tr>\n".format(interface, *vs['physical_interfaces'][interface])
                    for element in vs['physical_interfaces'][interface]:
                        if '(secured)' in element:
                            numsec += 1
                if numsec != numsecrequired:
                    output_html("<span style='color:red; font-weight: bold'>Insufficient secure interfaces - {}</span>".format(numsec))
                output_html('{}\n</table>'.format(physlist))
            else:
                output_html("No Physical Interfaces found.<br />")
            # print the virtual interfaces
            if 'virtual_cluster_interfaces' in vs.keys():
                output_html("""<h4>{} Virtual Interfaces</h4>\n<table>""".format(vs['virtual_cluster_interfaces']))
                for interface in sorted(vs['virtual_interfaces']):
                    output_html("<tr><td>{}</td><td>{}</td></tr>".format(interface, *vs['virtual_interfaces'][interface]))
                    pass
                output_html("</table>")
            else:
                output_html("No Virtual Interfaces found.<br />")
            # identify the list of vlans for this vs
            vs_vlans = [ vlan for vlan in vlans.keys() if full_vsid in vlans[vlan]]
            # show them
            if vs_vlans:
                graph = "graph TD"
                output_html("<h4>Vlan list</h4>\n<table><tr><th>Vlan</th><th>Connects To</th></tr>")
                for v in sorted(vs_vlans, key=int):
                    output_html("<tr><td>{}</td>".format(v))
                    # find if it shares with other vs'
                    if len(vlans[v]) > 1:
                        # add vlan links to the graph
                        for vs in vlans[v]:
                            if vs != full_vsid:
                                graph += "\n{}---|{}|{}".format(get_vsname_by_id(full_vsid),v,get_vsname_by_id(vs))
                        # add html info
                        output_html( "<td>")
                        output_html(", ".join([ link_to_vs_by_id(vs) for vs in vlans[v] if vs != full_vsid ]))
                    else:
                        # add a leaf node to the graph
                        output_html("<td>directly connected</td>")
                        graph += "\nVLAN{} --- {}".format(v, get_vsname_by_id(full_vsid))
                    output_html("</td></tr>")
                output_html("</table>")
                if DOGRAPHS and graph != "graph TD":
                    # generate the per-VS graphs
                    with open('graph_files/{}.txt'.format(full_vsid), 'w') as fh:
                        fh.write(graph)
                    # generate the clickable link to show the graph

                    output_html("<div id='{}'><br />".format(full_vsid.replace('+','_')))
                    output_html("<button type='button' class='btn btn-primary' onclick=\"loadGraph('{0}')\">".format(full_vsid.replace('+','_')))
                    output_html("Click here to display connection graph for {}</button></p>\n\n".format(vsname))
                    output_html("</button></div>")


###################################
# Physical interfaces
###################################

output_html("<h1>Physical Interfaces</h1>")
output_html("<table><tr>")
# show a list per-gateway
for gateway in sorted(gateways):
    output_html("<td valign='top' colspan='2'><h3>{}</h3></a></td></tr>".format(gateway))
    # pull the interfaces
    for interface in sorted([ i for i in physinterfaces if i.startswith(gateway) ]):
        phys_links = []
        for full_vsid in physinterfaces[interface]:
            phys_links.append( '<a href="#{}">{}</a>'.format( full_vsid, get_vsname_by_id(full_vsid) ))
        # the name doesn't need the gateway
        interface = interface.replace('{}-'.format(gateway),'')
        output_html("<tr><th>{}</th><td>{}</</td></tr>".format(interface, " - ".join(phys_links)))
    #output_html("</ul></td>")
output_html("</table>")
    
###################################
# Full VLANs list
###################################

output_html("<h1>VLANs</h1>")
vlan_count = 0
output_html('<table style="border: 0px"><tr><td style="border: 0px"><table>')
for vlan in sorted(vlans, key=int):
    vlan_links = []
    for full_vsid in vlans[vlan]:
        vlan_links.append( '<a href="#{}"><button type="button" class="btn btn-default">{}</button></a>'.format( full_vsid, get_vsname_by_id(full_vsid) ))
    
    output_html("<tr><th>{}</th><td>{}</tr>".format(vlan, " - ".join([ link.replace("_VS_", " ") for link in vlan_links])))
    vlan_count = vlan_count + 1
    if vlan_count > len(vlans.keys()) / 3:
        vlan_count = 0
        #output_html('<ul></td><td><ul>')
        output_html('</table></td><td style="border: 0px" valign="top"><table>')
    
#output_html('</ul>')
output_html("</table>")
output_html('</td></tr></table>')

if DO_BIG_GRAPH:

    graph = "graph LR"
    for vlan in sorted(vlans):
        # leaf vlan
        if len(vlans[vlan]) == 1:
            leaf_vlan = get_vsname_by_id(vlans[vlan][0])
            graph += "\n{} --- VLAN{}".format(leaf_vlan, vlan)
        else:
            for v in vlans[vlan]:
                others = [vl for vl in vlans[vlan] if v!=vl]
                for other in others:
                    if "{}---|{}|{}".format(get_vsname_by_id(other),vlan,get_vsname_by_id(v)) not in graph:
                        graph += "\n{}---|{}|{}".format(get_vsname_by_id(v),vlan,get_vsname_by_id(other))

    output_html("""<div class="mermaid">{}</div>""".format(graph))


output_html(open('templates/footer.html','r').read())
