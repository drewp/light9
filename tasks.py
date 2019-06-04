from invoke import task
import glob

bin_sources = [
        'bin/ascoltami2',
        'bin/captureDevice',
        'bin/collector',
        'bin/collector_loadtest.py',
        'bin/effecteval',
        'bin/effectsequencer',
        'bin/homepageConfig',
        'bin/inputdemo',
        'bin/inputquneo',
        'bin/keyboardcomposer',
        'bin/listsongs',
        'bin/musicPad',
        'bin/musictime',
        'bin/paintserver',
        'bin/picamserve',
        'bin/rdfdb',
        'bin/run_local.py',
        'bin/subcomposer',
        'bin/subserver',
        'bin/vidref',
        'bin/vidrefsetup',
        'bin/wavecurve',
    ]
def pkg_sources():
    return glob.glob('light9/**/*.py', recursive=True)

@task
def mypy(ctx):
    print('\n\n')
    def run(sources):
        ss = ' '.join(sources)
        ctx.run(f'MYPYPATH=stubs:/my/proj/rdfdb env/bin/mypy --check-untyped-defs {ss}',
                pty=True, warn=True)

    sources = ' '.join(bin_sources + pkg_sources())
    ctx.run(f'env/bin/flake8 --ignore=E115,E123,E124,E126,E225,E231,E261,E262,E265,E301,E302,E303,E305,E306,E401,E402,E501,E701,E731,W291,W293,W391,W504,E131,E125 {sources}', warn=True)

    sources = ' '.join(pkg_sources())
    run(['bin/collector'])
    run(['bin/rdfdb'])
    run(['bin/keyboardcomposer'])
    run(['bin/effectsequencer'])
    run(['bin/ascoltami2'])
    run(['bin/vidref'])
    #for src in bin_sources:
    #    print(f"mypy {src}")
    #    run([src])# + pkg_sources())
@task
def reformat(ctx):
    ctx.run("env/bin/yapf --verbose --parallel --in-place --style google light9/*.py light9/*/*.py `file --no-pad  bin/* | grep 'Python script' | perl -lpe 's/:.*//'`")
    
@task
def test(ctx):
    ctx.run('docker build -f Dockerfile.build -t light9_build:latest .')
    ctx.run('docker run --rm -it -v `pwd`:/opt light9_build:latest'
            ' nose2 -v light9.currentstategraphapi_test light9.graphfile_test',
            pty=True)
