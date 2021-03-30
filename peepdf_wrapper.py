
import sys
import subprocess
import json

def is_javascript_found(path):
    vulnerable_tokens = ['/JS', '/Javascript']

    print("Starting peepdf scan of %s." % path)

    peepdf_proc = subprocess.Popen(
        ["peepdf", path, "--json"],
        stderr=subprocess.STDOUT,
        stdout=subprocess.PIPE
    )
    output = peepdf_proc.communicate()[0].decode(encoding="utf-8", errors="replace")
    print("peepdf raw output:\n%s" % output)

    if peepdf_proc.returncode != 0:
        print("peepdf scan ended with errors.")
        sys.exit(1)

    raw_json_string = json.loads(output)

    try:
        analysis_result = raw_json_string['peepdf_analysis']['advanced'][0]['version_info']
    except KeyError as e:
        print("Key in json couldn't be found.\nError: {0}".format(e))
        sys.exit(1)

    if 'suspicious_elements' in analysis_result:
        suspisious_elements = analysis_result['suspicious_elements']['actions']
        for token in vulnerable_tokens:
            if token in suspisious_elements:
                return True

    return False