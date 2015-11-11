
# NOTE: this Vagrant file will work on linux; for all other machines
# Vagrant is starting a proxy VM and that machine will not be forwarding
# ports properly. try to run it as: FORWARD_DOCKER_PORTS='true' vagrant up


Vagrant.configure("2") do |config|

  #TODO: mount the folder as the user that owns the repo
  config.vm.synced_folder ".", "/vagrant", owner: 1000, group: 130

  config.vm.define "swtr" do |swtr|
    swtr.vm.provider "docker" do |d|
      d.cmd     = ["/sbin/my_init", "--enable-insecure-key", "--", "/bin/bash"]
      d.has_ssh = true
      d.name = "swtr"
      d.build_dir = '.'
      d.ports = ['5001:5000']
    end
  end

  config.ssh.username = "root"
  config.ssh.private_key_path = "insecure_key"

end
