#!/usr/bin/env python3
import logging
import optparse
import colorama
from colorama import Fore, Style
import os
import sys
import subprocess
import stat


# PRE-REQ:
# Run as admin
# dism.exe /online /enable-feature /featurename:Microsoft-Windows-Subsystem-Linux /all
# wsl --set-default-version 1
# wsl --list --online
# wsl --install -d OracleLinux_9_1
# wsl yum install genisoimage


# Create a custom logger
logger = logging.getLogger("logger")
# Set the level of this logger. INFO means that it will handle all messages with a level of INFO and above
logger.setLevel(logging.DEBUG)
# Create handlers
c_handler = logging.StreamHandler(stream=sys.stdout)
f_handler = logging.FileHandler('hv_export_cfg.log')
c_handler.setLevel(logging.DEBUG)
f_handler.setLevel(logging.DEBUG)
# Create formatters and add it to handlers
c_format = logging.Formatter('%(asctime)s - %(funcName)s - %(levelname)s - %(message)s')
f_format = logging.Formatter('%(asctime)s - %(funcName)s - %(levelname)s - %(message)s')
c_handler.setFormatter(c_format)
f_handler.setFormatter(f_format)
# Add handlers to the logger
logger.addHandler(c_handler)
logger.addHandler(f_handler)

def get_arguments():
    parser = optparse.OptionParser()
    parser.add_option("-s", "--serverlist", dest="serverlist",
                      help="File name must be specified, the file must be located in same directory as the script \n The file should contain the list of hosts that will be created in the Hyper-V env. for example: \n #server_name,ip_address,subnet_mask,default_gw,dns_server \n server1,10.0.0.40,255.255.255.0,10.0.0.1,8.8.8.8")
    parser.add_option("-k", "--kickstarttemplate", dest="kickstarttemplate",
                      help="File name must be specified, the file must be located in same directory as the script \n a kickstart template with <SERVER_NAME>,<IP_ADDRESS>,<SUBNET_MASK>,<DEFAULT_GW>,<DNS_SERVER>")
    parser.add_option("-l", "--labdirectory", dest="labdirectory",
                      help="Enter the directory path that will be used for the LAB VMs - e.g. D:\\VM_LAB\\")
    parser.add_option("-i", "--isofile", dest="isofile",
                      help="Enter the ISO file full path for installing Linux. e.g D:\\VM_LAB\\OracleLinux-R9-U2-x86_64-dvd.iso")
    parser.add_option("-e", "--extractediso", dest="extractediso",
                      help="Enter the extracted ISO full path. e.g. D:\\extracted_iso\\ this folder will be created by the script")
    parser.add_option("-n", "--vmnet", dest="vmnet",
                      help="Enter the Hyper-V switch name, e.g. NAT")
    (options, arguments) = parser.parse_args()
    if not options.serverlist:
        parser.exit("[-] File name must be specified, the file must be located in same directory as the script \n The file should contain the list of hosts that will be created in the Hyper-V env. for example: \n #server_name,ip_address,subnet_mask,default_gw,dns_server \n server1,10.0.0.40,255.255.255.0,10.0.0.1,8.8.8.8")
    elif not options.kickstarttemplate:
        parser.exit("[-] File name must be specified, a kickstart template with <SERVER_NAME>,<IP_ADDRESS>,<SUBNET_MASK>,<DEFAULT_GW>,<DNS_SERVER>")
    elif not options.labdirectory:
        parser.exit("[-] Enter the directory path that will be used for the LAB VMs - e.g. D:\\VM_LAB\\")
    elif not options.isofile:
        parser.exit("[-] Enter the ISO file full path for installing Linux. e.g D:\\VM_LAB\\OracleLinux-R9-U2-x86_64-dvd.iso")
    elif not options.extractediso:
        parser.exit("[-] Enter the extracted ISO full path. e.g. D:\\extracted_iso\\ this folder will be created by the script")
    elif not options.vmnet:
        parser.exit("[-] Enter the Hyper-V switch name, e.g. NAT")
    return options

user_input = get_arguments()
list_of_servers_to_create = user_input.serverlist
kickstart_tmpl_file_name = user_input.kickstarttemplate
labdirectory = user_input.labdirectory
isofile = user_input.isofile
extractediso_dir = user_input.extractediso
vmnet = user_input.vmnet

def create_serverlist(list_of_servers_to_create):
    logger.info("\n[+] The script will create the following servers based on the file " + Fore.BLUE + list_of_servers_to_create + Style.RESET_ALL + ": ")
    serverlist = []
    with open(list_of_servers_to_create, 'r') as hosts_file:
        hosts_data = hosts_file.read()
    hosts_data = hosts_data.splitlines()
    logger.info(Fore.GREEN + str(hosts_data[0].split(",")) + Style.RESET_ALL)
    for server in hosts_data[1:]:
        server = server.split(",")
        logger.info(Fore.GREEN + str(server) + Style.RESET_ALL)
        serverlist.append(server)
    return serverlist

def read_kickstart_tmpl_file(kickstart_tmpl_file_name):
    logger.info("\n[+] The script will use the following kickstart template file: " + Fore.BLUE + kickstart_tmpl_file_name + Style.RESET_ALL + " (which should be located in the same directory as the script) \nand replace: " + Fore.GREEN + "<SERVER_NAME>,<IP_ADDRESS>,<SUBNET_MASK>,<DEFAULT_GW>,<DNS_SERVER>" + Style.RESET_ALL + " with the values above for each server in the list")
    with open(kickstart_tmpl_file_name, 'r') as ks_tmpl_file:
        ks_tmpl_data = ks_tmpl_file.readlines()
    return ks_tmpl_data

def print_and_log_additional_info(labdirectory, isofile, extractediso_dir):
    logger.info("\n[+] The script will use the following directory: " + Fore.BLUE +  labdirectory + Style.RESET_ALL + " to create the virtual machines, reserve enough free space for that")
    logger.info("\n[+] The script will use the following ISO file to install Linux OS: " + Fore.BLUE +  isofile + Style.RESET_ALL + " The file will be extracted here:")
    logger.info("\n[+] Extracted ISO directory " + Fore.BLUE + extractediso_dir + Style.RESET_ALL + " reserve enough free space for that")

def create_iso_mount_dir(extractediso_dir):
    # Create a temporary directory to mount the ISO
    logger.info("Creating a directory to extract the ISO: " + extractediso_dir)
    try:
        os.makedirs(extractediso_dir, exist_ok=True)
    except:
        logger.error("Failed to create a directory: " + extractediso_dir)

def mount_iso(isofile):
# Mount the ISO
    try:
        logger.info("Attempting to mount ISO " + isofile)
        mount = subprocess.check_output(["PowerShell", "Mount-DiskImage", isofile, "-PassThru", "|", "Get-Volume"])
        mount = mount.decode().splitlines()
        isofile_mount_drive_latter = mount[3].split()[0]
        isofile_mount_drive_latter = isofile_mount_drive_latter + ":\\\\"
        logger.info("Linux installer was mounted on drive latter: " + isofile_mount_drive_latter)
    except:
        logger.error("Failed to mount ISO " + isofile)
    return isofile_mount_drive_latter

def copy_files_from_mounted_iso(isofile_mount_drive_latter, extractediso_dir):
    # Copy the contents of the ISO to the temporary directory
    extractediso_dir = extractediso_dir.replace("\\", "\\\\")
    try:
        logger.info("Attempting to copy mounted ISO " + isofile_mount_drive_latter + " to " + extractediso_dir)
        copy_iso_files_to_extractediso_dir = subprocess.check_output(["PowerShell", "Copy-Item", "-Path", isofile_mount_drive_latter + "*", "-Destination", extractediso_dir, "-Recurse", "-Force"])
        logger.info("Copied mounted ISO " + isofile_mount_drive_latter + " to " + extractediso_dir)
    except:
        logger.error("Failed to copy mounted ISO " + isofile_mount_drive_latter + " to " + extractediso_dir)

def unmount_iso(isofile):
    # Unmount the ISO
    try:
        logger.info("Attempting to unmount ISO " + isofile)
        umount = subprocess.check_output(["PowerShell", "Dismount-DiskImage", "-ImagePath", isofile])
        logger.info("Unmounted ISO " + isofile)
    except:
        logger.info("Failed to unmount ISO " + isofile)

def create_kickstart_file(lab_kickstart_template, servername, ip, subnet, gw, dns):
    #replace <SERVER_NAME>,<IP_ADDRESS>,<SUBNET_MASK>,<DEFAULT_GW>,<DNS_SERVER> with values
    kickstart_file = []
    for i, line in enumerate(lab_kickstart_template):
        line = line.replace("<SERVER_NAME>", servername)
        line = line.replace("<IP_ADDRESS>", ip)
        line = line.replace("<SUBNET_MASK>", subnet)
        line = line.replace("<DEFAULT_GW>", gw)
        line = line.replace("<DNS_SERVER>", dns)
        kickstart_file.append(line)
    return kickstart_file

def read_grub_file(extractediso_dir):
    grub_file_full_path = extractediso_dir + "EFI\\BOOT\\grub.cfg"
    with open(grub_file_full_path, 'r') as grub:
        grub_data = grub.readlines()
    return grub_data

def modify_grub_file(lab_orig_grub):
    done = False
    new_grab_file = []
    for i, line in enumerate(lab_orig_grub):
        if "search" in line:
            label = line.split()[-1].replace("'","")
        if "linuxefi" in line:
            if not "check" in line:
                if not "rescue" in line:
                    if not "text" in line:
                        if not done:
                            line = line.replace("quiet", "quiet inst.ks=hd:LABEL=" + label + ":/ks.cfg")
                            done = True
        if "set default" in line:
            line = line.replace("1", "0")
        if "set timeout" in line:
            line = line.replace("60", "5")
        new_grab_file.append(line)
    return new_grab_file

def get_label(lab_orig_grub):
    for i, line in enumerate(lab_orig_grub):
        if "search" in line:
            label = line.split()[-1].replace("'","")
    return label

def replace_grub_file_with_modified(extractediso_dir, lab_modified_grub_file):
    grub_file_full_path_to_replace_file = extractediso_dir + "EFI\\BOOT\\grub.cfg"
    os.chmod(grub_file_full_path_to_replace_file, stat.S_IWRITE)
    with open(grub_file_full_path_to_replace_file, 'w', newline='\n') as g:
        g.writelines(lab_modified_grub_file)

def build_iso(extractediso_dir, lab_label, labdirectory, servername):
    # lab_label = "\"" + lab_label + "\""
    print(lab_label)
    labdirectory_lnx = labdirectory.replace(":","")
    labdirectory_lnx = labdirectory_lnx.replace("\\", "/")
    labdirectory_tmp = labdirectory_lnx.split("/")
    labdirectory_tmp[0]=labdirectory_tmp[0].lower()
    labdirectory_lnx = "/".join(labdirectory_tmp)
    labdirectory_lnx = "/mnt/" + labdirectory_lnx
    outfile = labdirectory_lnx + servername + ".iso"
    print(outfile)
    script_path = os.path.abspath(__file__)
    script_dir = os.path.dirname(script_path)
    extractediso_dir_lnx = extractediso_dir.replace(":","")
    extractediso_dir_lnx = extractediso_dir_lnx.replace("\\", "/")
    extractediso_dir_tmp = extractediso_dir_lnx.split("/")
    extractediso_dir_tmp[0] = extractediso_dir_tmp[0].lower()
    extractediso_dir_lnx = "/".join(extractediso_dir_tmp)
    extractediso_dir_lnx = "/mnt/" + extractediso_dir_lnx
    print(extractediso_dir_lnx)
    os.chdir(extractediso_dir)
    # output_of_cmd = subprocess.check_output(["dir"], shell=True)
    build = subprocess.check_output(["wsl.exe", "genisoimage", "-U", "-r", "-v", "-T", "-J", "-joliet-long", "-V", lab_label, "-volset", lab_label, "-A", lab_label, "-b", "isolinux/isolinux.bin", "-c", "isolinux/boot.cat", "-no-emul-boot", "-boot-load-size", "4", "-boot-info-table", "-eltorito-alt-boot", "-e", "images/efiboot.img", "-no-emul-boot", "-o", outfile, extractediso_dir_lnx, "."])
    os.chdir(script_dir)
    return build

lab_server_list = create_serverlist(list_of_servers_to_create)
lab_kickstart_template = read_kickstart_tmpl_file(kickstart_tmpl_file_name)
print_and_log_additional_info(labdirectory, isofile, extractediso_dir)
create_iso_mount_dir(extractediso_dir)
lab_iso_mount_drive_latter = mount_iso(isofile)
copy_files_from_mounted_iso(lab_iso_mount_drive_latter, extractediso_dir)
unmount_iso(isofile)
lab_orig_grub = read_grub_file(extractediso_dir)
lab_modified_grub_file = modify_grub_file(lab_orig_grub)
replace_grub_file_with_modified(extractediso_dir, lab_modified_grub_file)
lab_label = get_label(lab_orig_grub)

for lab_server in lab_server_list:
    vm_memory = "4GB"
    vm_cpu = "8"
    ks = create_kickstart_file(lab_kickstart_template, lab_server[0],lab_server[1], lab_server[2], lab_server[3], lab_server[4])
    # file_name = lab_server[0] + "_ks.cfg"
    file_name = "ks.cfg"
    with open(file_name, 'w', newline='\n') as f:
        f.writelines(ks)
    copy_ks_to_extracted_iso = subprocess.check_output(["PowerShell", "Copy-Item", " -Path", file_name, "-Destination", extractediso_dir])
    build_iso_file = build_iso(extractediso_dir, lab_label, labdirectory, lab_server[0])
    newvm = subprocess.check_output(["PowerShell", "New-VM", "-Name", lab_server[0], "-Generation", "2", "-SwitchName", vmnet])
    vhdpath = labdirectory + lab_server[0] + "\\\\" + lab_server[0] + ".vhdx"
    print(vhdpath)
    newvhd = subprocess.check_output(["PowerShell", "New-VHD", "-Path", vhdpath, "-Dynamic", "-SizeBytes", "1024GB"])
    addvhd = subprocess.check_output(["PowerShell", "ADD-VMHardDiskDrive", "-VMName", lab_server[0], "-Path", vhdpath])
    staticmem = subprocess.check_output(["PowerShell", "Set-VM", "-VMName", lab_server[0], "-StaticMemory"])
    setmem = subprocess.check_output(["PowerShell", "Set-VM", "-VMName", lab_server[0], "-MemoryStartupBytes", vm_memory])
    setfw = subprocess.check_output(["PowerShell", "Set-VMFirmware", "-VMName", lab_server[0], "-EnableSecureBoot", "Off"])
    setautoshut = subprocess.check_output(["PowerShell", "Set-VM", "-VMName", lab_server[0], "-AutomaticStopAction", "Shutdown"])
    setcpu = subprocess.check_output(["PowerShell", "Set-VM", "-VMName", lab_server[0], "-ProcessorCount", vm_cpu])
    isopath = labdirectory + lab_server[0] + ".iso"
    adddvd = subprocess.check_output(["PowerShell", "Add-VMDvdDrive", "-VMName", lab_server[0], "-Path", isopath])
    vm_name = lab_server[0]
    cmd = f'powershell -Command "Set-VMFirmware -VMName {vm_name} -FirstBootDevice $(Get-VMDvdDrive -VMName {vm_name})"'
    setdvdboot = subprocess.run(cmd, shell=True)
    startvm = subprocess.check_output(["PowerShell", "Start-VM", "-VMName", lab_server[0]])
