# Report

This schema defines the Report entity. Reports are static information computed from data periodically that includes data in text, table, and visual form.

**$id: **[**https://open-metadata.org/schema/entity/data/report.json**](https://open-metadata.org/schema/entity/data/report.json)

Type: `object`

## Properties

* **id** `required`
  * Unique identifier that identifies this report.
  * $ref: [../../type/basic.json#/definitions/uuid](../types/basic.md#uuid)
* **name** `required`
  * Name that identifies this report instance uniquely.
  * Type: `string`
  * Length: between 1 and 64
* **fullyQualifiedName**
  * A unique name that identifies a report in the format 'ServiceName.ReportName'.
  * Type: `string`
  * Length: between 1 and 64
* **displayName**
  * Display Name that identifies this report. It could be title or label from the source services.
  * Type: `string`
* **description**
  * Description of this report instance.
  * Type: `string`
* **version**
  * Metadata version of the entity.
  * $ref: [../../type/basic.json#/definitions/entityVersion](../types/basic.md#entityversion)
* **updatedAt**
  * Last update time corresponding to the new version of the entity.
  * $ref: [../../type/basic.json#/definitions/dateTime](../types/basic.md#datetime)
* **updatedBy**
  * User who made the update.
  * Type: `string`
* **href**
  * Link to the resource corresponding to this report.
  * $ref: [../../type/basic.json#/definitions/href](../types/basic.md#href)
* **owner**
  * Owner of this pipeline.
  * $ref: [../../type/entityReference.json](../types/entityreference.md)
* **service** `required`
  * Link to service where this report is hosted in.
  * $ref: [../../type/entityReference.json](../types/entityreference.md)
* **usageSummary**
  * Latest usage information for this database.
  * $ref: [../../type/usageDetails.json](../types/usagedetails.md)

_This document was updated on: Monday, October 18, 2021_
