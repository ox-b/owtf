"""
owtf.db.poutput_manager
~~~~~~~~~~~~~~~~~~~~~~~

"""

import os
import json

from sqlalchemy.exc import SQLAlchemyError

from owtf.dependency_management.dependency_resolver import BaseComponent
from owtf.dependency_management.interfaces import PluginOutputInterface
from owtf.managers.target import target_required
from owtf.managers.session import session_required
from owtf.lib.exceptions import InvalidParameterType
from owtf.db import models
from owtf.utils import FileOperations


class POutputDB(BaseComponent, PluginOutputInterface):

    COMPONENT_NAME = "plugin_output"

    def __init__(self):
        self.register_in_service_locator()
        self.config = self.get_component("config")
        self.plugin_handler = self.get_component("plugin_handler")
        self.reporter = self.get_component("reporter")
        self.target = self.get_component("target")
        self.db_config = self.get_component("db_config")
        self.timer = self.get_component("timer")
        self.db = self.get_component("db")

    def plugin_output_exists(self, plugin_key, target_id):
        """Check if output exists

        :param plugin_key: plugin key
        :type plugin_key: `str`
        :param target_id: Target id
        :type target_id: `int`
        :return: True if count > 0
        :rtype: `bool`
        """
        count = self.db.session.query(models.PluginOutput).filter_by(target_id=target_id, plugin_key=plugin_key).count()
        return (count > 0)

    def plugin_count_output(self):
        """Get count stats

        :return: Count stats
        :rtype: `dict`
        """
        complete_count = self.db.session.query(models.PluginOutput).count()
        left_count = self.db.session.query(models.Work).count()
        left_count += self.get_component("worker_manager").get_busy_workers()
        results = {'complete_count': complete_count, 'left_count': left_count}
        return results

    def get_html_output(self, plugin_output):
        """Get html output

        :param plugin_output: Plugin output
        :type plugin_output: `list`
        :return: HTML string
        :rtype: `str`
        """
        content = ''
        for item in plugin_output:
            content += getattr(self.reporter, item["type"])(**item["output"])
        return content

    @target_required
    def get_output_dict(self, obj, target_id=None, inc_output=False):
        """Gets plugin outputs as dict

        :param obj: output obj
        :type obj:
        :param target_id: target ID
        :type target_id: `int`
        :param inc_output: Is there?
        :type inc_output: `bool`
        :return: Plugin output as a dict
        :rtype: `dict`
        """
        if target_id:
            self.target.set_target(target_id)
        if obj:
            pdict = dict(obj.__dict__)
            pdict.pop("_sa_instance_state", None)
            pdict.pop("date_time")
            # If output is present, json decode it
            if inc_output:
                if pdict.get("output", None):
                    pdict["output"] = self.get_html_output(json.loads(pdict["output"]))
            else:
                pdict.pop("output")
            pdict["start_time"] = obj.start_time.strftime(self.db_config.get("DATE_TIME_FORMAT"))
            pdict["end_time"] = obj.end_time.strftime(self.db_config.get("DATE_TIME_FORMAT"))
            pdict["run_time"] = self.timer.get_time_as_str(obj.run_time)
            return pdict

    @target_required
    def get_output_dicts(self, obj_list, target_id=None, inc_output=False):
        """Get plugin output dicts from a list of objects

        :param obj_list: List of objects
        :type obj_list: `list`
        :param target_id: target ID
        :type target_id: `int`
        :param inc_output: True/false
        :type inc_output: `bool`
        :return: List of output dicts
        :rtype: `list`
        """
        if target_id:
            self.target.set_target(target_id)
        dict_list = []
        for obj in obj_list:
            dict_list.append(self.get_output_dict(obj, target_id=target_id, inc_output=inc_output))
        return dict_list

    def gen_query(self, filter_data, target_id, for_delete=False):
        """Generate query

        :param filter_data: Filter criteria
        :type filter_data: `dict`
        :param target_id: target ID
        :type target_id: `int`
        :param for_delete: For deletion?
        :type for_delete: `bool`
        :return:
        :rtype:
        """
        query = self.db.session.query(models.PluginOutput).filter_by(target_id=target_id)
        if filter_data.get("target_id", None):
            query.filter_by(target_id=filter_data["target_id"])
        if filter_data.get("plugin_key", None):
            if isinstance(filter_data.get("plugin_key"), str):
                query = query.filter_by(plugin_key=filter_data["plugin_key"])
            if isinstance(filter_data.get("plugin_key"), list):
                query = query.filter(models.PluginOutput.plugin_key.in_(filter_data["plugin_key"]))
        if filter_data.get("plugin_type", None):
            if isinstance(filter_data.get("plugin_type"), str):
                query = query.filter_by(plugin_type=filter_data["plugin_type"])
            if isinstance(filter_data.get("plugin_type"), list):
                query = query.filter(models.PluginOutput.plugin_type.in_(filter_data["plugin_type"]))
        if filter_data.get("plugin_group", None):
            if isinstance(filter_data.get("plugin_group"), str):
                query = query.filter_by(plugin_group=filter_data["plugin_group"])
            if isinstance(filter_data.get("plugin_group"), list):
                query = query.filter(models.PluginOutput.plugin_group.in_(filter_data["plugin_group"]))
        if filter_data.get("plugin_code", None):
            if isinstance(filter_data.get("plugin_code"), str):
                query = query.filter_by(plugin_code=filter_data["plugin_code"])
            if isinstance(filter_data.get("plugin_code"), list):
                query = query.filter(models.PluginOutput.plugin_code.in_(filter_data["plugin_code"]))
        if filter_data.get("status", None):
            if isinstance(filter_data.get("status"), str):
                query = query.filter_by(status=filter_data["status"])
            if isinstance(filter_data.get("status"), list):
                query = query.filter(models.PluginOutput.status.in_(filter_data["status"]))
        try:
            if filter_data.get("user_rank", None):
                if isinstance(filter_data.get("user_rank"), str):
                    query = query.filter_by(user_rank=int(filter_data["user_rank"]))
                if isinstance(filter_data.get("user_rank"), list):
                    numbers_list = [int(x) for x in filter_data["user_rank"]]
                    query = query.filter(models.PluginOutput.user_rank.in_(numbers_list))
            if filter_data.get("owtf_rank", None):
                if isinstance(filter_data.get("owtf_rank"), str):
                    query = query.filter_by(owtf_rank=int(filter_data["owtf_rank"]))
                if isinstance(filter_data.get("owtf_rank"), list):
                    numbers_list = [int(x) for x in filter_data["owtf_rank"]]
                    query = query.filter(models.PluginOutput.owtf_rank.in_(numbers_list))
        except ValueError:
            raise InvalidParameterType("Integer has to be provided for integer fields")
        if not for_delete:
            query = query.order_by(models.PluginOutput.plugin_key.asc())
        try:
            if filter_data.get("offset", None):
                if isinstance(filter_data.get("offset"), list):
                    query = query.offset(int(filter_data["offset"][0]))
            if filter_data.get("limit", None):
                if isinstance(filter_data.get("limit"), list):
                    query = query.limit(int(filter_data["limit"][0]))
        except ValueError:
            raise InvalidParameterType("Integer has to be provided for integer fields")
        return query

    @target_required
    def get_all(self, filter_data=None, target_id=None, inc_output=False):
        """Get all data based on criteria

        :param filter_data: Filter data
        :type filter_data: `dict`
        :param target_id: target ID
        :type target_id: `int`
        :param inc_output: true/false
        :type inc_output: `bool`
        :return: list of output dicts
        :rtype: `list`
        """
        if not filter_data:
            filter_data = {}
        self.target.set_target(target_id)
        query = self.gen_query(filter_data, target_id)
        results = query.all()
        return self.get_output_dicts(results, target_id=target_id, inc_output=inc_output)

    @target_required
    def get_unique(self, target_id=None):
        """Returns a dict of some column names and their unique database, useful for advanced filter

        :param target_id: target ID
        :type target_id: `int`
        :return: Results
        :rtype: `dict`
        """
        unique_data = {
            "plugin_type": [i[0] for i in self.db.session.query(models.PluginOutput.plugin_type).filter_by(
                target_id=target_id).distinct().all()],
            "plugin_group": [i[0] for i in self.db.session.query(models.PluginOutput.plugin_group).filter_by(
                target_id=target_id).distinct().all()],
            "status": [i[0] for i in self.db.session.query(models.PluginOutput.status).filter_by(
                target_id=target_id).distinct().all()],
            "user_rank": [i[0] for i in self.db.session.query(models.PluginOutput.user_rank).filter_by(
                target_id=target_id).distinct().all()],
            "owtf_rank": [i[0] for i in self.db.session.query(models.PluginOutput.owtf_rank).filter_by(
                target_id=target_id).distinct().all()],
        }
        return unique_data

    @target_required
    def delete_all(self, filter_data, target_id=None):
        """Delete all plugin output

        .note::
            Here keeping filter_data optional is very risky

        :param filter_data: Filter data
        :type filter_data: `dict`
        :param target_id: target ID
        :type target_id: `int`
        :return: None
        :rtype: None
        """
        # for_delete = True: empty dict will match all results
        query = self.gen_query(filter_data, target_id, for_delete=True)
        # Delete the folders created for these plugins
        for plugin in query.all():
            # First check if path exists in db
            if plugin.output_path:
                output_path = os.path.join(self.config.get_output_dir_target(), plugin.output_path)
                if os.path.exists(output_path):
                    FileOperations.rm_tree(output_path)
        # When folders are removed delete the results from db
        results = query.delete()
        self.db.session.commit()

    @target_required
    def update(self, plugin_group, plugin_type, plugin_code, patch_data, target_id=None):
        """Update output in DB

        :param plugin_group: Plugin group
        :type plugin_group: `str`
        :param plugin_type: Plugin type
        :type plugin_type: `str`
        :param plugin_code: Plugin code
        :type plugin_code: `str`
        :param patch_data: Patched data
        :type patch_data: `dict`
        :param target_id: target ID
        :type target_id: `int`
        :return: None
        :rtype: None
        """
        plugin_dict = {"plugin_group": plugin_group, "plugin_type": plugin_type, "plugin_code": plugin_code}
        query = self.gen_query(plugin_dict, target_id)
        obj = query.first()
        if obj:
            try:
                if patch_data.get("user_rank", None):
                    if isinstance(patch_data["user_rank"], list):
                        patch_data["user_rank"] = patch_data["user_rank"][0]
                    obj.user_rank = int(patch_data["user_rank"])
                    obj.owtf_rank = -1
                if patch_data.get("user_notes", None):
                    if isinstance(patch_data["user_notes"], list):
                        patch_data["user_notes"] = patch_data["user_notes"][0]
                    obj.user_notes = patch_data["user_notes"]
                self.db.session.merge(obj)
                self.db.session.commit()
            except ValueError:
                raise InvalidParameterType("Integer has to be provided for integer fields")

    def plugin_already_run(self, plugin_info, target_id=None):
        """Check if plugin already ran

        :param plugin_info: Plugin info
        :type plugin_info: `dict`
        :param target_id: target ID
        :type target_id: `int`
        :return: True if already ran
        :rtype: `bool`
        """
        plugin_output_count = self.db.session.query(models.PluginOutput).filter_by(
            target_id=target_id,
            plugin_code=plugin_info["code"],
            plugin_type=plugin_info["type"],
            plugin_group=plugin_info["group"]).count()
        return plugin_output_count > 0  # This is nothing but a "None" returned

    @target_required
    def save_plugin_output(self, plugin, output, target_id=None):
        """Save into the database the command output of the plugin.

        :param plugin: Plugin dict
        :type plugin: `dict`
        :param output: Plugin output
        :type output: `str`
        :param target_id: target ID
        :type target_id: `int`
        :return: None
        :rtype: None
        """
        self.db.session.merge(models.PluginOutput(
            plugin_key=plugin["key"],
            plugin_code=plugin["code"],
            plugin_group=plugin["group"],
            plugin_type=plugin["type"],
            output=json.dumps(output),
            start_time=plugin["start"],
            end_time=plugin["end"],
            status=plugin["status"],
            target_id=target_id,
            # Save path only if path exists i.e if some files were to be stored it will be there
            output_path=(plugin["output_path"] if os.path.exists(
                self.plugin_handler.get_plugin_output_dir(plugin)) else None),
            owtf_rank=plugin['owtf_rank'])
        )
        try:
            self.db.session.commit()
        except SQLAlchemyError as e:
            self.db.session.rollback()
            raise e

    @target_required
    def save_partial_output(self, plugin, output, message, target_id=None):
        """Save partial plugin output

        :param plugin: Plugin dict
        :type plugin: `dict`
        :param output: Output
        :type output: `str`
        :param message: Message
        :type message: `str`
        :param target_id: target ID
        :type target_id: `int`
        :return: None
        :rtype: None
        """
        self.db.session.merge(models.PluginOutput(
            plugin_key=plugin["key"],
            plugin_code=plugin["code"],
            plugin_group=plugin["group"],
            plugin_type=plugin["type"],
            output=json.dumps(output),
            error=message,
            start_time=plugin["start"],
            end_time=plugin["end"],
            status=plugin["status"],
            target_id=target_id,
            # Save path only if path exists i.e if some files were to be stored it will be there
            output_path=(plugin["output_path"] if os.path.exists(
                self.plugin_handler.get_plugin_output_dir(plugin)) else None),
            owtf_rank=plugin['owtf_rank'])
        )
        try:
            self.db.session.commit()
        except SQLAlchemyError as e:
            self.db.session.rollback()
            raise e

    @session_required
    def get_severity_freq(self, session_id=None):
        """Get severity frequencies for the analytics

        :param session_id: session ID
        :type session_id: `int`
        :return: Frequency data
        :rtype: `dict`
        """
        severity_frequency = [
            {"id": 0, "label": "Passing", "value": 0},
            {"id": 1, "label": "Info", "value": 0},
            {"id": 2, "label": "Low", "value": 0},
            {"id": 3, "label": "Medium", "value": 0},
            {"id": 4, "label": "High", "value": 0},
            {"id": 5, "label": "Critical", "value": 0},
        ]

        targets = []
        target_objs = self.db.session.query(models.Target.id).filter(models.Target.sessions.any(id=session_id)).all()
        for target_obj in target_objs:
            targets.append(target_obj.id)

        plugin_objs = self.db.session.query(models.PluginOutput).all()

        for plugin_obj in plugin_objs:
            if plugin_obj.target_id in targets:
                if plugin_obj.user_rank != -1:
                    severity_frequency[plugin_obj.user_rank]["value"] += 1
                else:
                    if plugin_obj.owtf_rank != -1:
                        # Removing the not ranked plugins
                        severity_frequency[plugin_obj.owtf_rank]["value"] += 1

        return {"data": severity_frequency[::-1]}
