from django.dispatch import Signal

post_commit = Signal()
post_push = Signal()
post_pull = Signal()
post_sync = Signal()

post_create_branch = Signal()
post_delete_branch = Signal()
post_rename_branch = Signal()


