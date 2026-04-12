We are continuing an existing project on a reComputer R1035-10.

Project summary:
- Ubuntu Server installed on NVMe SSD
- eMMC failover planned
- LTE connectivity
- Tailscale remote access
- Cockpit on 9090
- Docker stack with Portainer, Grafana, Prometheus, Node Exporter
- Pi-hole, Samba, VirtualHere
- Custom containerized network portal
- One service LAN port was selected for field-service use
- Portal includes controls to disable internet access on that port to save LTE data
- Remote access is mainly through Tailscale
- Current issue: carrier started enforcing IPv6 and the system currently only handles IPv4 routing
- Next goal: add IPv6-aware routing/firewalling and continue improving the portal

Please inspect the repo and help continue from here.
