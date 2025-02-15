---
description: >-
  This guide will help install ElasticSearch connector and run manually to index
  the metadata stored in OpenMetadata.
---

# ElasticSearch

{% hint style="info" %}
**Prerequisites**

OpenMetadata is built using Java, DropWizard, Jetty, and MySQL.

1. Python 3.7 or above
{% endhint %}

### Install from PyPI

{% tabs %}
{% tab title="Install Using PyPI" %}
```bash
pip install 'openmetadata-ingestion[elasticsearch]'
```
{% endtab %}
{% endtabs %}

## Run Manually

```bash
metadata ingest -c ./examples/workflows/metadata_to_es.json
```

### Configuration

{% code title="metadata_to_es.json" %}
```javascript
{
  "source": {
    "type": "metadata_es",
    "config": {}
  },
...
```
{% endcode %}

### Publish to OpenMetadata

Below is the configuration to publish Elastic Search data into the OpenMetadata service.

Add Optionally `file` stage and `elasticsearch` bulk\_sink along with `metadata-server` config

{% code title="metadata_to_es.json" %}
```javascript
{
  "source": {
    "type": "metadata_es",
    "config": {}
  },
  "stage": {
    "type": "file",
    "config": {
      "filename": "/tmp/tables.txt"
    }
  },
  "bulk_sink": {
    "type": "elasticsearch",
    "config": {
      "filename": "/tmp/tables.txt",
      "es_host_port": "localhost",
      "index_name": "table_search_index"
    }
  },
  "metadata_server": {
    "type": "metadata-server",
    "config": {
      "api_endpoint": "http://localhost:8585/api",
      "auth_provider_type": "no-auth"
    }
  }
}
```
{% endcode %}
