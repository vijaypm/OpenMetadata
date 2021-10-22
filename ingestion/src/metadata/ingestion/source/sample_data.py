#  Licensed to the Apache Software Foundation (ASF) under one or more
#  contributor license agreements. See the NOTICE file distributed with
#  this work for additional information regarding copyright ownership.
#  The ASF licenses this file to You under the Apache License, Version 2.0
#  (the "License"); you may not use this file except in compliance with
#  the License. You may obtain a copy of the License at
#
#  http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.

import csv
import json
import logging
import os
import uuid
from collections import namedtuple
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Union

from faker import Faker
from pydantic import ValidationError

from metadata.config.common import ConfigModel
from metadata.generated.schema.api.data.createTopic import CreateTopicEntityRequest
from metadata.generated.schema.api.lineage.addLineage import AddLineage
from metadata.generated.schema.api.services.createDashboardService import (
    CreateDashboardServiceEntityRequest,
)
from metadata.generated.schema.api.services.createDatabaseService import (
    CreateDatabaseServiceEntityRequest,
)
from metadata.generated.schema.api.services.createMessagingService import (
    CreateMessagingServiceEntityRequest,
)
from metadata.generated.schema.api.services.createPipelineService import (
    CreatePipelineServiceEntityRequest,
)
from metadata.generated.schema.entity.data.database import Database
from metadata.generated.schema.entity.data.model import Model
from metadata.generated.schema.entity.data.pipeline import Pipeline
from metadata.generated.schema.entity.data.table import Table
from metadata.generated.schema.entity.data.task import Task
from metadata.generated.schema.entity.services.dashboardService import DashboardService
from metadata.generated.schema.entity.services.databaseService import DatabaseService
from metadata.generated.schema.entity.services.messagingService import MessagingService
from metadata.generated.schema.entity.services.pipelineService import PipelineService
from metadata.generated.schema.type.entityLineage import EntitiesEdge
from metadata.generated.schema.type.entityReference import EntityReference
from metadata.ingestion.api.common import Record
from metadata.ingestion.api.source import Source, SourceStatus
from metadata.ingestion.models.ometa_table_db import OMetaDatabaseAndTable
from metadata.ingestion.models.table_metadata import Chart, Dashboard
from metadata.ingestion.ometa.openmetadata_rest import (
    MetadataServerConfig,
    OpenMetadataAPIClient,
)
from metadata.utils.helpers import get_database_service_or_create

logger: logging.Logger = logging.getLogger(__name__)

COLUMN_NAME = "Column"
KEY_TYPE = "Key type"
DATA_TYPE = "Data type"
COL_DESCRIPTION = "Description"
TableKey = namedtuple("TableKey", ["schema", "table_name"])


class InvalidSampleDataException(Exception):
    """
    Sample data is not valid to be ingested
    """


def get_database_service_or_create(service_json, metadata_config) -> DatabaseService:
    client = OpenMetadataAPIClient(metadata_config)
    service = client.get_database_service(service_json["name"])
    if service is not None:
        return service
    else:
        created_service = client.create_database_service(
            CreateDatabaseServiceEntityRequest(**service_json)
        )
        return created_service


def get_messaging_service_or_create(service_json, metadata_config) -> MessagingService:
    client = OpenMetadataAPIClient(metadata_config)
    service = client.get_messaging_service(service_json["name"])
    if service is not None:
        return service
    else:
        created_service = client.create_messaging_service(
            CreateMessagingServiceEntityRequest(**service_json)
        )
        return created_service


def get_dashboard_service_or_create(service_json, metadata_config) -> DashboardService:
    client = OpenMetadataAPIClient(metadata_config)
    service = client.get_dashboard_service(service_json["name"])
    if service is not None:
        return service
    else:
        created_service = client.create_dashboard_service(
            CreateDashboardServiceEntityRequest(**service_json)
        )
        return created_service


def get_pipeline_service_or_create(service_json, metadata_config) -> PipelineService:
    client = OpenMetadataAPIClient(metadata_config)
    service = client.get_pipeline_service(service_json["name"])
    if service is not None:
        return service
    else:
        created_service = client.create_pipeline_service(
            CreatePipelineServiceEntityRequest(**service_json)
        )
        return created_service


def get_lineage_entity_ref(edge, metadata_config) -> EntityReference:
    client = OpenMetadataAPIClient(metadata_config)
    fqn = edge["fqn"]
    if edge["type"] == "table":
        table = client.get_table_by_name(fqn)
        return EntityReference(id=table.id, type="table")
    elif edge["type"] == "pipeline":
        pipeline = client.get_pipeline_by_name(edge["fqn"])
        return EntityReference(id=pipeline.id, type="pipeline")
    elif edge["type"] == "dashboard":
        dashboard = client.get_dashboard_by_name(fqn)
        return EntityReference(id=dashboard.id, type="dashboard")


def get_table_key(row: Dict[str, Any]) -> Union[TableKey, None]:
    """
    Table key consists of schema and table name
    :param row:
    :return:
    """
    return TableKey(schema=row["schema"], table_name=row["table_name"])


class SampleDataSourceConfig(ConfigModel):
    sample_data_folder: str
    service_name: str = "bigquery_gcp"
    database: str = "warehouse"
    service_type: str = "BigQuery"
    scheme = "bigquery+pymysql"

    def get_sample_data_folder(self):
        return self.sample_data_folder


@dataclass
class SampleDataSourceStatus(SourceStatus):
    success: List[str] = field(default_factory=list)
    failures: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

    def scanned(self, entity_type: str, entity_name: str) -> None:
        self.success.append(entity_name)
        logger.info("{} Scanned: {}".format(entity_type, entity_name))

    def filtered(self, entity_type: str, entity_name: str, err: str) -> None:
        self.warnings.append(entity_name)
        logger.warning("Dropped {} {} due to {}".format(entity_type, entity_name, err))


class TableSchema:
    def __init__(self, filename):
        # error if the file is not csv file
        if not filename.endswith(".csv"):
            raise Exception("Input file should be a csv file")

        # file name is assumed to be the table name
        basename = os.path.basename(filename)
        self.table_name = os.path.splitext(basename)[0]

        with open(filename, "r") as fin:
            self.columns = [dict(i) for i in csv.DictReader(fin)]

    def primary_keys(self):
        return [c[COLUMN_NAME] for c in self.columns if c[KEY_TYPE] == "PK"]

    def foreign_keys(self):
        return [c[COLUMN_NAME] for c in self.columns if c[KEY_TYPE] == "FK"]

    def get_name(self):
        return self.table_name

    def get_schema(self):
        return self.columns

    def get_column_names(self):
        return [c[COLUMN_NAME] for c in self.columns]


class SampleTableMetadataGenerator:
    def __init__(self, table_to_df_dict, table_to_schema_map):
        self.table_to_df_dict = table_to_df_dict
        self.table_to_schema_map = table_to_schema_map
        self.sample_user = None
        self.sample_table = None
        self.sample_table_owner = None
        self.sample_table_last_updated = None

    def get_empty_dict_with_cols(self, columns):
        data = {}
        for c in columns:
            data[c] = []
        return data


class GenerateFakeSampleData:
    def __init__(self) -> None:
        pass

    @classmethod
    def check_columns(self, columns):
        fake = Faker()
        colData = []
        colList = [column["name"] for column in columns]
        for i in range(25):
            row = []
            for column in columns:
                col_name = column["name"]
                value = None
                if "id" in col_name:
                    value = uuid.uuid4()
                elif "price" in col_name or "currency" in col_name:
                    value = fake.pricetag()
                elif "barcode" in col_name:
                    value = fake.ean(length=13)
                elif "phone" in col_name:
                    value = fake.phone_number()
                elif "zip" in col_name:
                    value = fake.postcode()
                elif "address" in col_name:
                    value = fake.street_address()
                elif "company" in col_name:
                    value = fake.company()
                elif "region" in col_name:
                    value = fake.street_address()
                elif "name" in col_name:
                    value = fake.first_name()
                elif "city" in col_name:
                    value = fake.city()
                elif "country" in col_name:
                    value = fake.country()
                if value is None:
                    if "TIMESTAMP" in column["dataType"] or "date" in col_name:
                        value = fake.unix_time()
                    elif "BOOLEAN" in column["dataType"]:
                        value = fake.pybool()
                    elif "NUMERIC" in column["dataType"]:
                        value = fake.pyint()
                    elif "VARCHAR" in column["dataType"]:
                        value = fake.text(max_nb_chars=20)
                    else:
                        value = None
                row.append(value)
            colData.append(row)
        return {"columns": colList, "rows": colData}


class SampleDataSource(Source):
    def __init__(
        self, config: SampleDataSourceConfig, metadata_config: MetadataServerConfig, ctx
    ):
        super().__init__(ctx)
        self.status = SampleDataSourceStatus()
        self.config = config
        self.metadata_config = metadata_config
        self.client = OpenMetadataAPIClient(metadata_config)
        self.database_service_json = json.load(
            open(self.config.sample_data_folder + "/datasets/service.json", "r")
        )
        self.database = json.load(
            open(self.config.sample_data_folder + "/datasets/database.json", "r")
        )
        self.tables = json.load(
            open(self.config.sample_data_folder + "/datasets/tables.json", "r")
        )
        self.database_service = get_database_service_or_create(
            self.database_service_json, self.metadata_config
        )
        self.kafka_service_json = json.load(
            open(self.config.sample_data_folder + "/topics/service.json", "r")
        )
        self.topics = json.load(
            open(self.config.sample_data_folder + "/topics/topics.json", "r")
        )
        self.kafka_service = get_messaging_service_or_create(
            self.kafka_service_json, self.metadata_config
        )
        self.dashboard_service_json = json.load(
            open(self.config.sample_data_folder + "/dashboards/service.json", "r")
        )
        self.charts = json.load(
            open(self.config.sample_data_folder + "/dashboards/charts.json", "r")
        )
        self.dashboards = json.load(
            open(self.config.sample_data_folder + "/dashboards/dashboards.json", "r")
        )
        self.dashboard_service = get_dashboard_service_or_create(
            self.dashboard_service_json, metadata_config
        )
        self.pipeline_service_json = json.load(
            open(self.config.sample_data_folder + "/pipelines/service.json", "r")
        )
        self.tasks = json.load(
            open(self.config.sample_data_folder + "/pipelines/tasks.json", "r")
        )
        self.pipelines = json.load(
            open(self.config.sample_data_folder + "/pipelines/pipelines.json", "r")
        )
        self.pipeline_service = get_pipeline_service_or_create(
            self.pipeline_service_json, metadata_config
        )
        self.lineage = json.load(
            open(self.config.sample_data_folder + "/lineage/lineage.json", "r")
        )
        self.models = json.load(
            open(self.config.sample_data_folder + "/models/models.json", "r")
        )

    @classmethod
    def create(cls, config_dict, metadata_config_dict, ctx):
        config = SampleDataSourceConfig.parse_obj(config_dict)
        metadata_config = MetadataServerConfig.parse_obj(metadata_config_dict)
        return cls(config, metadata_config, ctx)

    def prepare(self):
        pass

    def next_record(self) -> Iterable[Record]:
        yield from self.ingest_tables()
        yield from self.ingest_topics()
        yield from self.ingest_charts()
        yield from self.ingest_dashboards()
        yield from self.ingest_tasks()
        yield from self.ingest_pipelines()
        yield from self.ingest_lineage()
        yield from self.ingest_models()

    def ingest_tables(self) -> Iterable[OMetaDatabaseAndTable]:
        db = Database(
            id=uuid.uuid4(),
            name=self.database["name"],
            description=self.database["description"],
            service=EntityReference(
                id=self.database_service.id, type=self.config.service_type
            ),
        )
        for table in self.tables["tables"]:
            if not table.get("sampleData"):
                table["sampleData"] = GenerateFakeSampleData.check_columns(
                    table["columns"]
                )
            table_metadata = Table(**table)
            table_and_db = OMetaDatabaseAndTable(table=table_metadata, database=db)
            self.status.scanned("table", table_metadata.name.__root__)
            yield table_and_db

    def ingest_topics(self) -> Iterable[CreateTopicEntityRequest]:
        for topic in self.topics["topics"]:
            topic["service"] = EntityReference(
                id=self.kafka_service.id, type="messagingService"
            )
            create_topic = CreateTopicEntityRequest(**topic)
            self.status.scanned("topic", create_topic.name.__root__)
            yield create_topic

    def ingest_charts(self) -> Iterable[Chart]:
        for chart in self.charts["charts"]:
            try:
                chart_ev = Chart(
                    name=chart["name"],
                    displayName=chart["displayName"],
                    description=chart["description"],
                    chart_type=chart["chartType"],
                    url=chart["chartUrl"],
                    service=EntityReference(
                        id=self.dashboard_service.id, type="dashboardService"
                    ),
                )
                self.status.scanned("chart", chart_ev.name)
                yield chart_ev
            except ValidationError as err:
                logger.error(err)

    def ingest_dashboards(self) -> Iterable[Dashboard]:
        for dashboard in self.dashboards["dashboards"]:
            dashboard_ev = Dashboard(
                name=dashboard["name"],
                displayName=dashboard["displayName"],
                description=dashboard["description"],
                url=dashboard["dashboardUrl"],
                charts=dashboard["charts"],
                service=EntityReference(
                    id=self.dashboard_service.id, type="dashboardService"
                ),
            )
            self.status.scanned("dashboard", dashboard_ev.name)
            yield dashboard_ev

    def ingest_tasks(self) -> Iterable[Task]:
        for task in self.tasks["tasks"]:
            task_ev = Task(
                id=uuid.uuid4(),
                name=task["name"],
                displayName=task["displayName"],
                description=task["description"],
                taskUrl=task["taskUrl"],
                taskType=task["taskType"],
                downstreamTasks=task["downstreamTasks"],
                service=EntityReference(
                    id=self.pipeline_service.id, type="pipelineService"
                ),
            )
            yield task_ev

    def ingest_pipelines(self) -> Iterable[Dashboard]:
        tasks = self.client.list_tasks("service")
        task_dict = {}
        for task in tasks:
            task_dict[task.name] = task

        for pipeline in self.pipelines["pipelines"]:
            task_refs = []
            for task in pipeline["tasks"]:
                if task in task_dict:
                    task_refs.append(
                        EntityReference(id=task_dict[task].id, type="task")
                    )
            pipeline_ev = Pipeline(
                id=uuid.uuid4(),
                name=pipeline["name"],
                displayName=pipeline["displayName"],
                description=pipeline["description"],
                pipelineUrl=pipeline["pipelineUrl"],
                tasks=task_refs,
                service=EntityReference(
                    id=self.pipeline_service.id, type="pipelineService"
                ),
            )
            yield pipeline_ev

    def ingest_lineage(self) -> Iterable[AddLineage]:
        for edge in self.lineage:
            from_entity_ref = get_lineage_entity_ref(edge["from"], self.metadata_config)
            to_entity_ref = get_lineage_entity_ref(edge["to"], self.metadata_config)
            lineage = AddLineage(
                edge=EntitiesEdge(fromEntity=from_entity_ref, toEntity=to_entity_ref)
            )
            yield lineage

    def ingest_models(self) -> Iterable[Model]:
        """
        Convert sample model data into a Model Entity
        to feed the metastore
        """
        for model in self.models:
            # Fetch linked dashboard ID from name
            dashboard_name = model["dashboard"]
            dashboard_id = next(
                iter(
                    [
                        dash["id"]
                        for dash in self.dashboards["dashboards"]
                        if dash["name"] == dashboard_name
                    ]
                ),
                None,
            )

            if not dashboard_id:
                raise InvalidSampleDataException(
                    f"Cannot find {dashboard_name} in Sample Dashboards"
                )

            model_ev = Model(
                id=uuid.uuid4(),
                name=model["name"],
                displayName=model["displayName"],
                description=model["description"],
                algorithm=model["algorithm"],
                dashboard=EntityReference(id=dashboard_id, type="dashboard"),
            )

            yield model_ev

    def close(self):
        pass

    def get_status(self):
        return self.status
