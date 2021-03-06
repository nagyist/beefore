###########################################################################
# Check if any of the Python files touched by the commit have
# code style problems.
###########################################################################
import os.path
import requests
import sys
import subprocess

from beefore import diff


LABEL = 'PyCodeStyle'
DESCRIPTION = {
    'pending': 'Checking Python code style...',
    'success': 'Code meets Python style standards!',
    'failure': 'Found some Python code style problems.',
    'error': 'Error while checking Python code style.',
}


class Lint:
    def __init__(self, filename, line, col, code, description):
        self.filename = filename
        self.line = line
        self.col = col
        self.code = code
        self.description = description

    def __str__(self):
        return 'Line %s, col %s: [%s] %s' % (self.line, self.col, self.code, self.description)

    def add_comment(self, pull_request, commit, position):
        pull_request.create_review_comment(
            body="At column %(col)d: [(%(code)s) %(description)s](http://.../%(code)s)" % {
                'col': self.col,
                'code': self.code,
                'description': self.description
            },
            commit_id=commit.sha,
            path=self.filename,
            position=position,
        )

    @staticmethod
    def find(filename, content, config):
        cmd_line = [
            sys.executable, '-m', 'flake8',
            '--config', '.flake8.ini',
            '--stdin-display-name', filename,
            '-'
        ]

        proc = subprocess.Popen(
            cmd_line,
            cwd=os.path.dirname(os.path.abspath(sys.argv[1])),
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE
        )
        out, err = proc.communicate(content)

        out_lines = out.decode('utf-8').strip().split('\n')

        problems = []
        for problem in out_lines:
            fname, line, col, remainder = problem.split(':', 4)
            code, description = remainder.strip().split(' ', 1)
            problems.append(Lint(
                filename=filename,
                line=int(line),
                col=int(col),
                code=code,
                description=description,
            ))

        return problems


def check(pull_request, commit, directory, config):
    problem_found = False

    diff_content = pull_request.diff().decode('utf-8').split('\n')

    for changed_file in commit.files:
        if os.path.splitext(changed_file['filename'])[-1] == '.py':
            print ("  * %s" % changed_file['filename'])

            # Build a map of line numbers to diff positions
            diff_position = diff.positions(diff_content, changed_file['filename'])

            # If a directory has been provided, use that as the source of
            # the files. Otherwise, download the file blob.
            if directory is None:
                response = requests.get(changed_file['raw_url'])
                content = response.content
            else:
                with open(os.path.join(directory, changed_file['filename'])) as fp:
                    content = fp.read().encode('utf-8')

            problems = Lint.find(
                filename=changed_file['filename'],
                content=content,
                config=config
            )

            for problem in problems:
                try:
                    position = diff_position[problem.line]
                    print('    - %s' % problem)
                    problem.add_comment(pull_request, commit, position)
                except KeyError:
                    # Line doesn't exist in the diff; so we can ignore this problem
                    pass

    return problem_found
