from datetime import date

from controllers.base_controller import BaseController
from dtos import SampleEntityDTO
from errors import (
    DuplicatedDocumentNumber,
    DuplicatedEmail,
    InvalidBirthdate,
    InvalidDocumentNumber,
    InvalidParameter,
    NotFoundSampleEntity,
    SampleEntityFinalStatus,
    UnderageSampleEntity,
)
from models import SampleEntity, SampleEntityStatus
from repositories import SampleEntityRepository
from utils.document_number import is_valid_cpf

# A faixa de idade aceita. Abaixo do mínimo o cadastro é RECUSADO; acima
# do máximo ele é CRIADO, mas já em "failed" — são desfechos diferentes,
# e o create lá embaixo mostra a diferença em duas linhas.
MINIMUM_AGE = 18
MAXIMUM_AGE = 80


class SampleEntityController(BaseController):

    def __init__(self) -> None:
        super().__init__(__name__)
        self.sample_entity_repository = SampleEntityRepository(self.context)

    def create(self, sample_entity_data: dict) -> dict:
        
        self.logger.debug("Criando uma nova Sample Entity")

        document_number = sample_entity_data["document_number"]
        email = sample_entity_data["email"]
        birthdate = self._parse_birthdate(sample_entity_data["birthdate"])

        if not is_valid_cpf(document_number):
            raise InvalidDocumentNumber(document_number)

        if self.sample_entity_repository.get_by_document_number(document_number) is not None:
            raise DuplicatedDocumentNumber(document_number)

        if self.sample_entity_repository.get_by_email(email) is not None:
            raise DuplicatedEmail(email)

        age = self._age_in_years(birthdate)

        if age < MINIMUM_AGE:
            raise UnderageSampleEntity(age, MINIMUM_AGE)

        sample_entity = self.sample_entity_repository.create(sample_entity_data=sample_entity_data)

        if age > MAXIMUM_AGE:
            new_status = SampleEntityStatus.FAILED
        else:
            new_status = SampleEntityStatus.PENDING

        self.sample_entity_repository.update_status(sample_entity, new_status)

        sample_entity_dto = SampleEntityDTO.only_obj_key(sample_entity)
        self.session.commit()

        return sample_entity_dto

    def get_by_key(self, sample_entity_key: str) -> dict:
        self.logger.debug(f"Buscando a entidade de chave {sample_entity_key}")

        sample_entity = self.sample_entity_repository.get_by_key(sample_entity_key)

        if sample_entity is None:
            raise NotFoundSampleEntity(sample_entity_key)

        return SampleEntityDTO.obj_to_dict(sample_entity)

    def get_list(self, limit: int, offset: int, filters: dict) -> dict:
        
        birthdate_from = filters.get("birthdate_from")
        birthdate_to = filters.get("birthdate_to")

        if birthdate_from is not None:
            birthdate_from = self._parse_birthdate(birthdate_from)
            filters["birthdate_from"] = birthdate_from

        if birthdate_to is not None:
            birthdate_to = self._parse_birthdate(birthdate_to)
            filters["birthdate_to"] = birthdate_to

        if birthdate_from is not None and birthdate_to is not None:
            if birthdate_from > birthdate_to:
                raise InvalidParameter(
                    f"birthdate_from ({birthdate_from}) is after birthdate_to ({birthdate_to})"
                )

        sample_entities_list = self.sample_entity_repository.list_page(limit, offset, filters)

        
        is_last_page = True
        if len(sample_entities_list) > limit:
            is_last_page = False
            sample_entities_list = sample_entities_list[:-1]

        return {
            "sample_entities_list_dto": SampleEntityDTO.list_obj_to_list_dict(sample_entities_list),
            "is_last_page": is_last_page,
        }

    def update_status(self, sample_entity_key: str, new_status: str) -> dict:
        sample_entity = self.sample_entity_repository.get_by_key(sample_entity_key)

        if sample_entity is None:
            raise NotFoundSampleEntity(sample_entity_key)

        self._check_status_can_change(sample_entity, new_status)

        self.sample_entity_repository.update_status(sample_entity, new_status)

        sample_entity_dto = SampleEntityDTO.only_obj_key(sample_entity)
        self.session.commit()

        return sample_entity_dto

    def webhook_increment_counter(self, sample_entity_key: str) -> None:
        self.logger.debug(f"Processando webhook da entidade {sample_entity_key}")

        sample_entity = self.sample_entity_repository.get_by_key(sample_entity_key)

        if sample_entity is None:
            raise NotFoundSampleEntity(sample_entity_key)

        self.sample_entity_repository.increment_counter(sample_entity)

        self.session.commit()

    def _check_status_can_change(self, sample_entity: SampleEntity, new_status: str) -> None:
        old_status = sample_entity.status.enumerator

        if old_status != SampleEntityStatus.PENDING:
            raise SampleEntityFinalStatus(old_status, new_status)

    def _parse_birthdate(self, raw_birthdate: str) -> date:
        
        try:
            return date.fromisoformat(raw_birthdate)
        except ValueError:
            raise InvalidBirthdate(raw_birthdate)

    def _age_in_years(self, birthdate: date) -> int:
        today = date.today()
        age = today.year - birthdate.year

        if (today.month, today.day) < (birthdate.month, birthdate.day):
            age = age - 1

        return age
