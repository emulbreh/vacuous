import sys
from optparse import make_option
from django.core.management.base import BaseCommand, CommandError
from vacuous.adapters import iter_adapters
from vacuous.transactions import commit_on_success

class Command(BaseCommand):
    help = "Commits all changes to objects in the database"
    option_list = BaseCommand.option_list + (
        make_option('-m', dest='message', help='the commit message'),
    )
    def handle(self, message=None, **options):
        if not message:
            self.stderr.write("You must provide a commit message.\n")
            sys.exit(1)
        with commit_on_success(message=message):
            for adapter in iter_adapters():
                print "committing adapter", adapter
                try:
                    for obj in adapter.iter_objects():
                        print obj
                        adapter(obj).write()
                except Exception as e:
                    print e
        


