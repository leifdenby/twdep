import subprocess
import json
import rich
import rich.tree
import asciidag
import asciidag.node
import asciidag.graph
import time
import os


def get_tasks(uuid=None, filter_args=[]):
    if uuid is None:
        cmd = f"task {' '.join(filter_args)} export".split()
    else:
        cmd = f"task {uuid} export".split()
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE)
    s = p.communicate()[0].decode("unicode_escape")
    # TODO: there appears to be a bug in taskwarriors json output sometime with
    # nested lists
    s = s.replace('["["', '["').replace('"]"]', '"]')

    tasks_data = json.loads(s)
    tasks = {}
    for task_data in tasks_data:
        t_uuid = task_data["uuid"]
        tasks[t_uuid] = task_data
    return tasks


def _make_label(task_data, show_uuid):
    status = task_data["status"]
    if status in ["deleted", "completed"]:
        label = f"({status}): {task_data['description']}"
    else:
        label = f"{task_data['id']}: {task_data['description']}"

    if show_uuid:
        label += f" [{task_data['uuid']}]"
    return label


def main(filter_args, exclude_completed=False, show_uuid=False):
    tasks = get_tasks(filter_args=filter_args)
    root_name = len(filter_args) > 0 and " ".join(filter_args) or "tasks"

    missing_tasks = {}

    # work out which tasks have no dependencies and which have dependencies
    nodeps = []
    deps = {}
    for t_uuid, task_data in tasks.items():
        if "depends" not in task_data:
            nodeps.append(t_uuid)
        else:
            for td_uuid in task_data["depends"]:
                deps.setdefault(td_uuid, []).append(t_uuid)

    # look-up any tasks which are dependended on, but weren't part of the
    # original query result (these may be deleted or completed)
    for t_uuid in deps.keys():
        if t_uuid not in tasks:
            missing_tasks[t_uuid] = get_tasks(t_uuid)[t_uuid]

    root_node = asciidag.node.Node(root_name)
    nodes = {}
    has_children = set()

    for t_uuid in nodeps:
        task_data = tasks.pop(t_uuid)
        label = _make_label(task_data, show_uuid=show_uuid)
        node = asciidag.node.Node(label, parents=[root_node])
        nodes[t_uuid] = node

    for t_uuid, task_data in missing_tasks.items():
        label = _make_label(task_data, show_uuid=show_uuid)
        node = asciidag.node.Node(label)
        nodes[t_uuid] = node

    while len(tasks) > 0:
        task_data = None
        for t_uuid in list(tasks.keys()):
            parents_exist = all(
                [td_uuid in nodes for td_uuid in tasks[t_uuid]["depends"]]
            )

            if parents_exist:
                task_data = tasks.pop(t_uuid)
                break

        if task_data is not None:
            label = _make_label(task_data, show_uuid=show_uuid)
            parents = []
            parents = [nodes[td_uuid] for td_uuid in task_data["depends"]]
            has_children = has_children.union(task_data["depends"])
            node = asciidag.node.Node(label, parents=parents)
            nodes[t_uuid] = node
        else:
            rich.print(nodes)
            rich.print(tasks)
            raise Exception()

    tree = []
    for t_uuid, node in nodes.items():
        if t_uuid not in has_children:
            tree.append(node)

    asciidag.graph.Graph().show_nodes(tree)


if __name__ == "__main__":
    import argparse

    argparser = argparse.ArgumentParser()
    argparser.add_argument("filter", nargs="*")
    argparser.add_argument("--show-uuid", default=False, action="store_true")
    argparser.add_argument("--keep-open", default=False, action="store_true")
    args = argparser.parse_args()

    filter_args = args.filter

    def render_tree():
        main(filter_args=filter_args, show_uuid=args.show_uuid)

    if not args.keep_open:
        render_tree()
    else:
        while True:
            os.system("clear")
            render_tree()
            time.sleep(5)
