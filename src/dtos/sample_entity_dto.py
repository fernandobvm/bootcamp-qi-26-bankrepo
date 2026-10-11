from copy import deepcopy
from typing import List

from models import SampleEntity


class SampleEntityDTO:
    @staticmethod
    def obj_to_dict(sample_entity: SampleEntity) -> dict:
        sample_entity_dto = SampleEntityDTO.obj_to_simplified_dict(sample_entity)
        sample_entity_dto["status_events"] = []

        for status_event in sample_entity.status_events:
            status_event_dto = dict()
            status_event_dto["status"] = status_event.status.enumerator
            status_event_dto["event_datetime"] = status_event.event_datetime.isoformat()

            sample_entity_dto["status_events"].append(status_event_dto)

        return sample_entity_dto

    @staticmethod
    def obj_to_simplified_dict(sample_entity: SampleEntity) -> dict:
        dto = deepcopy(sample_entity.sample_entity_data)
        dto["sample_entity_key"] = sample_entity.sample_entity_key
        dto["name"] = sample_entity.name
        dto["email"] = sample_entity.email
        dto["document_number"] = sample_entity.document_number
        dto["birthdate"] = sample_entity.birthdate.isoformat()
        dto["status"] = sample_entity.status.enumerator
        dto["counter"] = sample_entity.counter

        return dto

    @staticmethod
    def list_obj_to_list_dict(sample_entities_list: List[SampleEntity]) -> List[dict]:
        sample_entities_dict_list = []

        for sample_entity in sample_entities_list:
            sample_entities_dict_list.append(
                SampleEntityDTO.obj_to_simplified_dict(sample_entity)
            )

        return sample_entities_dict_list

    @staticmethod
    def only_obj_key(sample_entity: SampleEntity) -> dict:
        dto = dict()
        dto["sample_entity_key"] = sample_entity.sample_entity_key

        return dto
