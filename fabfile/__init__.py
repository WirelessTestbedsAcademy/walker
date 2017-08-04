import time
from datetime import datetime
# from itertools import permutations
from itertools import product
from fabric.api import *
from fabric.exceptions import CommandTimeout
from fabric.decorators import runs_once
import pandas as pd
import fabfile.config as config # noqa
import fabfile.wifi as wifi # noqa
from fabfile.config import set_hosts  # noqa
from tqdm import tqdm_gui


@task()
def node_info():
    with settings(warn_only=True):
        run('cat /etc/twistprotected')
        run('ip a')
        run('iw dev')


@task()
@parallel()
def run_iperf():
    if env.hosts.index(env.host_string) == 0:
        try:
            run('iperf -s -i 1', timeout=15)
        except CommandTimeout:
            print('ending server')
    elif env.hosts.index(env.host_string) == 1:
        time.sleep(1)
        run('iperf -i 1 -t  10 -c {}'.format(env.hosts[0]))


@task()
@runs_once
def full_scan():
    execute(wifi.interfaces_create)
    with settings(parallel=True):
        phys = execute(wifi.get_devices)
    data = pd.DataFrame()
    ssid = 'twist-test'
    bar = tqdm_gui()
    for server in env.hosts:
        for phy, (channel, mode) in product(
                phys[server],
                zip([1, 48], ['g', 'a'])):
            print('############## {}, {}, {}, {}'.format(
                server, phy, channel, mode))
            # Setup
            try:
                execute(wifi.create_ap,
                    channel=channel,
                    hw_mode=mode,
                    ssid=ssid,
                    hosts=[server])
            except wifi.FabricRunException:
                print("Cannot setup AP")
                continue
            # Experiment
            scan = execute(wifi.scan,
                hosts=[x for x in env.hosts if x != server],
                tqdm_=bar)
            for scanner in scan:
                s = pd.DataFrame.from_dict(scan[scanner], orient='columns')
                if s.empty:
                    continue
                s.ix[s.ssid == ssid, 'ap'] = server
                s.ix[s.ssid == ssid, 'ap_dev'] = phy
                data = data.append(s, ignore_index=True)
            # Tear down
            execute(wifi.interfaces_create, hosts=[server])
    data.to_csv('data/scan_{}.csv'.format(datetime.now().isoformat()))
    print(data)


@task()
def check_reg():
    for reg in ['00', 'DE', 'US', 'EU']:
        sudo(f'iw reg set {reg}')
        run('iw phy'
            + ' | grep -e " MHz " -e "Wiphy"'
            + ' | grep -v -e "IR" -e "disabled"')
