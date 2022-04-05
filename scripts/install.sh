#!/usr/bin/env bash

echo -e "\nexport OCI_CLI_AUTH=instance_principal" >> ~/.bashrc
yum -y update && sudo yum -y upgrade
yum install -y deltarpm python36-oci-cli
timedatectl set-timezone America/Sao_Paulo
crontab schedule.cron
