# Network Panel

A containerized network management portal designed for a `reComputer R1035-10` running `Ubuntu Server` on NVMe SSD.

## Features

- LTE-aware network control
- Tailscale-based remote access
- Custom service LAN management
- Internet on/off controls for selected interfaces
- Dockerized deployment
- Monitoring and self-hosted service integration

## Stack

- Ubuntu Server
- Docker / Docker Compose
- Python backend
- Custom frontend
- Tailscale
- Cockpit
- Grafana
- Prometheus
- Node Exporter
- Pi-hole
- Samba
- VirtualHere

## Use Case

This platform is designed to work both as:
- a field-service edge device
- a home lab infrastructure node

It allows selective internet access control on service ports, which is especially useful when working with limited LTE data plans.

## In Progress

- IPv6 routing support
- Extended network control features
- APN and LTE management from the web UI
- Hotspot / LAN role switching

## Service LAN Configuration

The backend now ships its own Service LAN internet control scripts and can be configured through `docker-compose.yml` environment variables:

- `SERVICE_LAN_INTERFACE`
- `SERVICE_LAN_IPV4_GATEWAY`
- `SERVICE_LAN_IPV4_SUBNET`
- `SERVICE_LAN_DHCP_RANGE`
- `SERVICE_LAN_IPV6_GATEWAY`
- `SERVICE_LAN_IPV6_PREFIX`
- `SERVICE_LAN_ENABLE_IPV4`
- `SERVICE_LAN_ENABLE_IPV6`

When IPv6 is enabled, the container applies IPv6 forwarding and an `nftables` `ip6` masquerade rule for the configured Service LAN prefix in addition to the existing IPv4 NAT behavior.
