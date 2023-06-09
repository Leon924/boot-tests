#!/usr/bin/env python3

# This is a job launch script for boot tests

import os
import sys
from uuid import UUID

from gem5art.artifact import Artifact
from gem5art.run import gem5Run
from gem5art.tasks.tasks import run_gem5_instance
from itertools import starmap
from itertools import product
import multiprocessing as mp

packer = Artifact.registerArtifact(
    command='''wget https://releases.hashicorp.com/packer/1.4.3/packer_1.4.3_linux_amd64.zip;
    unzip packer_1.4.3_linux_amd64.zip;
    ''',
    typ='binary',
    name='packer',
    path='disk-image/packer',
    cwd='disk-image',
    documentation='Program to build disk images. Downloaded sometime in August from hashicorp.'
)

experiments_repo = Artifact.registerArtifact(
    command='git clone https://github.com/Leon924/boot_tests.git',
    typ='git repo',
    name='boot_tests',
    path='./',
    cwd='../',
    documentation='main experiments repo to run full system boot tests with gem5'
)

gem5_repo = Artifact.registerArtifact(
    command='git clone https://gem5.googlesource.com/public/gem5',
    typ='git repo',
    name='gem5',
    path='gem5/',
    cwd='./',
    documentation='cloned gem5 master branch from googlesource (Nov 18, 2019)'
)

m5_binary = Artifact.registerArtifact(
    command='scons build/x86/out/m5',
    typ='binary',
    name='m5',
    path='gem5/util/m5/build/x86/out/m5',
    cwd='gem5/util/m5',
    inputs=[gem5_repo,],
    documentation='m5 utility'
)

disk_image = Artifact.registerArtifact(
    command='./packer build boot-exit/boot-exit.json',
    typ='disk image',
    name='boot-disk',
    cwd='disk-image',
    path='disk-image/boot-exit/boot-exit-image/boot-exit',
    inputs=[packer, experiments_repo, m5_binary,],
    documentation='Ubuntu with m5 binary installed and root auto login'
)

gem5_binary = Artifact.registerArtifact(
    command='''cd gem5;
    git checkout d40f0bc579fb8b10da7181;
    scons build/X86/gem5.opt -j8
    ''',
    typ='gem5 binary',
    name='gem5',
    cwd='gem5/',
    path='gem5/build/X86/gem5.opt',
    inputs=[gem5_repo,],
    documentation='gem5 binary based on googlesource (Nov 18, 2019)'
)

gem5_binary_MESI_Two_Level = Artifact.registerArtifact(
    command='''cd gem5;
    git checkout d40f0bc579fb8b10da7181;
    scons build/X86_MESI_Two_Level/gem5.opt --default=X86 PROTOCOL=MESI_Two_Level SLICC_HTML=True -j8
    ''',
    typ='gem5 binary',
    name='gem5',
    cwd='gem5/',
    path='gem5/build/X86_MESI_Two_Level/gem5.opt',
    inputs=[gem5_repo,],
    documentation='gem5 binary based on googlesource (Nov 18, 2019)'
)

linux_repo = Artifact.registerArtifact(
    command='''git clone https://github.com/torvalds/linux.git;
    mv linux linux-stable''',
    typ='git repo',
    name='linux-stable',
    path='linux-stable/',
    cwd='./',
    documentation='linux kernel source code repo from Sep 23rd'
)

linuxes = ['5.2.3', '4.19.83', '4.14.134', '4.9.186', '4.4.186']
linux_binaries = {
    version: Artifact.registerArtifact(
                name=f'vmlinux-{version}',
                typ='kernel',
                path=f'linux-stable/vmlinux-{version}',
                cwd='linux-stable/',
                command=f'''git checkout v{version};
                cp ../linux-configs/config.{version} .config;
                make -j8;
                cp vmlinux vmlinux-{version};
                ''',
                inputs=[experiments_repo, linux_repo,],
                documentation=f"Kernel binary for {version} with simple "
                                 "config file",
            )
    for version in linuxes
}
def createRun(linux, boot_type, cpu, num_cpu, mem):
    
    if mem == 'MESI_TWO_LEVEL':
        gem5_path = 'gem5/build/X86_MESI_Two_Level/gem5.opt'
        gem5_artifact = gem5_binary_MESI_Two_Level
    else:
        gem5_path = gem5_binary.path
        gem5_artifact = gem5_binary

    return gem5Run.createFSRun(
                              'boot experiment',
                               gem5_path,
                               'configs-boot-tests/run_exit.py',
                               'results/run_exit/vmlinux-{}/boot-exit/{}/{}/{}/{}'.
                               format(linux, cpu, mem, num_cpu, boot_type),
                               gem5_artifact, gem5_repo, experiments_repo,
                               os.path.join('linux-stable', 'vmlinux'+'-'+linux),
                               'disk-image/boot-exit/boot-exit-image/boot-exit',
                               linux_binaries[linux], disk_image,
                               cpu, mem, num_cpu, boot_type,
                               timeout = 6*60*60 #6 hours
                               )
if __name__ == "__main__":

    boot_types = ['init', 'systemd']
    num_cpus = ['1', '2', '4', '8']
    cpu_types = ['atomic', 'simple', 'o3']
    mem_types = ['classic', 'MI_example', 'MESI_Two_Level']

        
    def worker(run):
        run.run()
        json = run.dumpsJson()
        print(json)

    jobs = []
    # For the cross product of tests, create a run object.
    runs = starmap(createRun, product(linuxes, boot_types, cpu_types, num_cpus, mem_types))
    # Run all of these experiments in parallel
    for run in runs:
        jobs.append(run)

    with mp.Pool(mp.cpu_count() // 2) as pool:
         pool.map(worker, jobs)


#        for boot_type in boot_types:
#            for cpu in cpu_types:
#                for num_cpu in num_cpus:
#                    for mem in mem_types:
#                        if mem == 'MESI_Two_Level':
#                            run = gem5Run.createFSRun(
#                                'boot experiment with MESI Two Level',
#                                'gem5/build/X86_MESI_Two_Level/gem5.opt',
#                                'configs-boot-tests/run_exit.py',
#                                'results/run_exit/vmlinux-{}/boot-exit/{}/{}/{}/{}'.
#                                format(linux, cpu, mem, num_cpu, boot_type),
#                                gem5_binary_MESI_Two_Level, gem5_repo, experiments_repo,
#                                os.path.join('linux-stable', 'vmlinux'+'-'+linux),
#                                'disk-image/boot-exit/boot-exit-image/boot-exit',
#                                linux_binaries[linux], disk_image,
#                                cpu, mem, num_cpu, boot_type,
#                                timeout = 6*60*60 #6 hours
#                                )
#                            run_gem5_instance.apply_async((run,))
#                        else:
#                            run = gem5Run.createFSRun(
#                                'boot experiment',
#                                'gem5/build/X86/gem5.opt',
#                                'configs-boot-tests/run_exit.py',
#                                'results/run_exit/vmlinux-{}/boot-exit/{}/{}/{}/{}'.
#                                format(linux, cpu, mem, num_cpu, boot_type),
#                                gem5_binary, gem5_repo, experiments_repo,
#                                os.path.join('linux-stable', 'vmlinux'+'-'+linux),
#                                'disk-image/boot-exit/boot-exit-image/boot-exit',
#                                linux_binaries[linux], disk_image,
#                                cpu, mem, num_cpu, boot_type,
#                                timeout = 6*60*60 #6 hours
#                                )
#                            run_gem5_instance.apply_async((run,))
