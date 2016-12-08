#
# Next part was generated by system-config-kickstart.
#
#platform=x86, AMD64, or Intel EM64T
#version=DEVEL
# Install OS instead of upgrade
install
# Keyboard layouts
keyboard 'us'
# Root password
rootpw --plaintext 123456
# System timezone
timezone Europe/Prague
# System language
lang en_US
# Firewall configuration
firewall --disabled
# System authorization information
auth  --useshadow  --passalgo=sha512
# Use text mode install
text
# SELinux configuration
selinux --enforcing
# Network information
network  --bootproto=dhcp --device=eth0
# System bootloader configuration
bootloader --location=mbr
# Clear the Master Boot Record
zerombr
# Partition clearing information
clearpart --all --initlabel

#
# Added options.
#
bootloader --location=mbr --append="console=tty0 console=ttyS0,115200" --timeout=1
services --disabled="rhnsd,rngd,bluetooth" --enabled="ovirt-guest-agent"
user --name=test --password=123456 --groups=wheel --plaintext
xconfig --startxonboot
# autopart
# ignoredisk --only-use=sda
# --size= — The minimum partition size in megabytes. Specify an integer value here such as 500. Do not append the number with MB.
# --grow= — Tells the partition to grow to fill available space (if any), or up to the maximum size setting.
part / --fstype=ext4 --grow --size=8000
part swap --grow --size=200
firstboot --disable
poweroff

#
# Packages.
#

%packages --default
@smart-card
spice-vdagent
virt-viewer
# Note
# ----
# Make a note why do you need a certain package when you add a new entry.
-subscription-manager # Remove subscription tool for customers.
%end

#
# Post.
#
%post --erroronfail --log=/root/ks-post.log

#
# Capturing kernel parameters.
#
set -- `cat /proc/cmdline`
for I in $*; do
    case "$I" in
    *=*) eval $I;;
    esac
done

#
# Remove password for root/test.
#
echo 'Remove password for root/test.'
passwd -d root
passwd -d test

#
# SSH permit login with empty passwords.
#
echo 'SSH permit login with empty passwords.'
sed -i '/PermitEmpty/aPermitEmptyPasswords yes' '/etc/ssh/sshd_config'

#
# Grub config.
#
echo 'Remove rhgb quiet in grub config.'
grubby --remove-args='rhgb quiet' --update-kernel="$(grubby --default-kernel)"

#
# CD-ROM udev rules.
#
echo 'Disable lock cdrom udev rules.'
sed -i '/--lock-media/s/^/#/' '/usr/lib/udev/rules.d/60-cdrom_id.rules' 2>/dev/null>&1

#
# Gnome autologin.
#
echo 'Enable Gnome autologin.'
cat > '/etc/gdm/custom.conf' << EOF
[daemon]
AutomaticLogin=test
AutomaticLoginEnable=True
EOF

#
# Yum repo.
#
url="$(cat '/proc/cmdline' | grep -oE 'http[^[:space:]]+')"
if [ -n "$url" ]; then
    echo 'Add yum repo.'
    cat > '/etc/yum.repos.d/install.repo' << EOF
[install]
name = install
baseurl = $url
enabled = 1
gpgcheck = 0
EOF
fi

#
# Screensaver for Gnome.
#
echo 'Disable screensaver for Gnome.'
cfg='xml:readwrite:/etc/gconf/gconf.xml.defaults'
gconftool-2 --direct --config-source "$cfg" --type bool \
    --set "/apps/gnome-screensaver/idle_activation_enabled" false
gconftool-2 --direct --config-source "$cfg" --type bool \
    --set "/apps/gnome-screensaver/lock_enabled" false
gconftool-2 --direct --config-source "$cfg" --type bool \
    --set "/apps/gnome-screensaver/logout_enabled" false
gconftool-2 --direct --config-source "$cfg" --type bool \
    --set "/apps/gnome-screensaver/status_message_enabled" false
gconftool-2 --direct --config-source "$cfg" --type int \
    --set "/apps/gnome-screensaver/cycle_delay" 180
gconftool-2 --direct --config-source "$cfg" --type int \
    --set "/apps/gnome-screensaver/idle_delay" 180
gconftool-2 --direct --config-source "$cfg" --type int \
    --set "/apps/gnome-screensaver/logout_delay" 180
gconftool-2 --direct --config-source "$cfg" --type int \
    --set "/apps/gnome-screensaver/power_management_delay" 180

#
# Remove ifname <-> MAC binding.
#
sed -i "s/^/#/g" /etc/udev/rules.d/70-persistent-net.rules

#
# Add RedHat certificates.
#
certs[1]='https://password.corp.redhat.com/cacert.crt'
certs[2]='https://password.corp.redhat.com/RH-IT-Root-CA.crt'
certs[3]='http://idm.spice.brq.redhat.com/ipa/config/ca.crt'
i=1
for cert in "${certs[@]}"; do
    name="${i}.crt"
    wget -O "$name" "$cert"
    cp "$name" "/etc/pki/ca-trust/source/anchors/"
    i=$((i+1))
done
update-ca-trust force-enable
update-ca-trust extract

%end
