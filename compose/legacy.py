import logging
import re

from .container import get_container_name, Container


log = logging.getLogger(__name__)


# TODO: remove this section when migrate_project_to_labels is removed
NAME_RE = re.compile(r'^([^_]+)_([^_]+)_(run_)?(\d+)$')

ERROR_MESSAGE_FORMAT = """
Compose found the following containers without labels:

{names_list}

As of Compose 1.3.0, containers are identified with labels instead of naming convention. If you want to continue using these containers, run:

    $ docker-compose migrate-to-labels

Alternatively, remove them:

    $ docker rm -f {rm_args}
"""


def check_for_legacy_containers(
        client,
        project,
        services,
        stopped=False,
        one_off=False):
    """Check if there are containers named using the old naming convention
    and warn the user that those containers may need to be migrated to
    using labels, so that compose can find them.
    """
    names = list(get_legacy_container_names(
        client,
        project,
        services,
        stopped=stopped,
        one_off=one_off))

    if names:
        raise LegacyContainersError(names)


class LegacyContainersError(Exception):
    def __init__(self, names):
        self.names = names

        self.msg = ERROR_MESSAGE_FORMAT.format(
            names_list="\n".join("    {}".format(name) for name in names),
            rm_args=" ".join(names),
        )

    def __unicode__(self):
        return self.msg

    __str__ = __unicode__


def add_labels(project, container, name):
    project_name, service_name, one_off, number = NAME_RE.match(name).groups()
    if project_name != project.name or service_name not in project.service_names:
        return
    service = project.get_service(service_name)
    service.recreate_container(container)


def migrate_project_to_labels(project):
    log.info("Running migration to labels for project %s", project.name)

    client = project.client
    for container in client.containers(all=True):
        name = get_container_name(container)
        if not is_valid_name(name):
            continue
        add_labels(project, Container.from_ps(client, container), name)


def get_legacy_container_names(
        client,
        project,
        services,
        stopped=False,
        one_off=False):

    for container in client.containers(all=stopped):
        name = get_container_name(container)
        for service in services:
            if has_container(project, service, name, one_off=one_off):
                yield name


def has_container(project, service, name, one_off=False):
    if not name or not is_valid_name(name, one_off):
        return False
    container_project, container_service, _container_number = parse_name(name)
    return container_project == project and container_service == service


def is_valid_name(name, one_off=False):
    match = NAME_RE.match(name)
    if match is None:
        return False
    if one_off:
        return match.group(3) == 'run_'
    else:
        return match.group(3) is None


def parse_name(name):
    match = NAME_RE.match(name)
    (project, service_name, _, suffix) = match.groups()
    return (project, service_name, int(suffix))
