from __future__ import annotations

import pytest
from _pytest.fixtures import FixtureRequest
from sqlalchemy import BIGINT, PrimaryKeyConstraint
from sqlalchemy.dialects import postgresql
from sqlalchemy.dialects.postgresql import JSON, JSONB
from sqlalchemy.engine import Engine
from sqlalchemy.schema import (
    CheckConstraint,
    Column,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    MetaData,
    Table,
    UniqueConstraint,
)
from sqlalchemy.sql.expression import text
from sqlalchemy.types import ARRAY, INTEGER, VARCHAR, Text

from sqlacodegen.generators import CodeGenerator, DeclarativeGenerator

from .conftest import validate_code


@pytest.fixture
def generator(
    request: FixtureRequest, metadata: MetaData, engine: Engine
) -> CodeGenerator:
    options = getattr(request, "param", [])
    return DeclarativeGenerator(metadata, engine, options)


def test_indexes(generator: CodeGenerator) -> None:
    simple_items = Table(
        "simple_items",
        generator.metadata,
        Column("id", INTEGER, primary_key=True),
        Column("number", INTEGER),
        Column("text", VARCHAR),
    )
    simple_items.indexes.add(Index("idx_number", simple_items.c.number))
    simple_items.indexes.add(
        Index("idx_text_number", simple_items.c.text, simple_items.c.number)
    )
    simple_items.indexes.add(Index("idx_text", simple_items.c.text, unique=True))

    validate_code(
        generator.generate(),
        """\
from typing import Optional

from sqlalchemy import Index, Integer, String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

class Base(DeclarativeBase):
    pass


class SimpleItems(Base):
    __tablename__ = 'simple_items'
    __table_args__ = (
        Index('idx_number', 'number'),
        Index('idx_text', 'text', unique=True),
        Index('idx_text_number', 'text', 'number')
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    number: Mapped[Optional[int]] = mapped_column(Integer)
    text: Mapped[Optional[str]] = mapped_column(String)
        """,
    )


def test_constraints(generator: CodeGenerator) -> None:
    Table(
        "simple_items",
        generator.metadata,
        Column("id", INTEGER, primary_key=True),
        Column("number", INTEGER),
        CheckConstraint("number > 0"),
        UniqueConstraint("id", "number"),
    )

    validate_code(
        generator.generate(),
        """\
from typing import Optional

from sqlalchemy import CheckConstraint, Integer, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

class Base(DeclarativeBase):
    pass


class SimpleItems(Base):
    __tablename__ = 'simple_items'
    __table_args__ = (
        CheckConstraint('number > 0'),
        UniqueConstraint('id', 'number')
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    number: Mapped[Optional[int]] = mapped_column(Integer)
        """,
    )


def test_onetomany(generator: CodeGenerator) -> None:
    Table(
        "simple_items",
        generator.metadata,
        Column("id", INTEGER, primary_key=True),
        Column("container_id", INTEGER),
        ForeignKeyConstraint(["container_id"], ["simple_containers.id"]),
    )
    Table(
        "simple_containers",
        generator.metadata,
        Column("id", INTEGER, primary_key=True),
    )

    validate_code(
        generator.generate(),
        """\
from typing import Optional

from sqlalchemy import ForeignKey, Integer
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

class Base(DeclarativeBase):
    pass


class SimpleContainers(Base):
    __tablename__ = 'simple_containers'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    simple_items: Mapped[list['SimpleItems']] = relationship('SimpleItems', \
back_populates='container')


class SimpleItems(Base):
    __tablename__ = 'simple_items'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    container_id: Mapped[Optional[int]] = \
mapped_column(ForeignKey('simple_containers.id'))

    container: Mapped[Optional['SimpleContainers']] = relationship('SimpleContainers', \
back_populates='simple_items')
    """,
    )


def test_onetomany_selfref(generator: CodeGenerator) -> None:
    Table(
        "simple_items",
        generator.metadata,
        Column("id", INTEGER, primary_key=True),
        Column("parent_item_id", INTEGER),
        ForeignKeyConstraint(["parent_item_id"], ["simple_items.id"]),
    )

    validate_code(
        generator.generate(),
        """\
from typing import Optional

from sqlalchemy import ForeignKey, Integer
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

class Base(DeclarativeBase):
    pass


class SimpleItems(Base):
    __tablename__ = 'simple_items'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    parent_item_id: Mapped[Optional[int]] = \
mapped_column(ForeignKey('simple_items.id'))

    parent_item: Mapped[Optional['SimpleItems']] = relationship('SimpleItems', \
remote_side=[id], back_populates='parent_item_reverse')
    parent_item_reverse: Mapped[list['SimpleItems']] = relationship('SimpleItems', \
remote_side=[parent_item_id], back_populates='parent_item')
""",
    )


def test_onetomany_selfref_multi(generator: CodeGenerator) -> None:
    Table(
        "simple_items",
        generator.metadata,
        Column("id", INTEGER, primary_key=True),
        Column("parent_item_id", INTEGER),
        Column("top_item_id", INTEGER),
        ForeignKeyConstraint(["parent_item_id"], ["simple_items.id"]),
        ForeignKeyConstraint(["top_item_id"], ["simple_items.id"]),
    )

    validate_code(
        generator.generate(),
        """\
from typing import Optional

from sqlalchemy import ForeignKey, Integer
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

class Base(DeclarativeBase):
    pass


class SimpleItems(Base):
    __tablename__ = 'simple_items'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    parent_item_id: Mapped[Optional[int]] = \
mapped_column(ForeignKey('simple_items.id'))
    top_item_id: Mapped[Optional[int]] = mapped_column(ForeignKey('simple_items.id'))

    parent_item: Mapped[Optional['SimpleItems']] = relationship('SimpleItems', \
remote_side=[id], foreign_keys=[parent_item_id], back_populates='parent_item_reverse')
    parent_item_reverse: Mapped[list['SimpleItems']] = relationship('SimpleItems', \
remote_side=[parent_item_id], foreign_keys=[parent_item_id], \
back_populates='parent_item')
    top_item: Mapped[Optional['SimpleItems']] = relationship('SimpleItems', remote_side=[id], \
foreign_keys=[top_item_id], back_populates='top_item_reverse')
    top_item_reverse: Mapped[list['SimpleItems']] = relationship('SimpleItems', \
remote_side=[top_item_id], foreign_keys=[top_item_id], back_populates='top_item')
        """,
    )


def test_onetomany_composite(generator: CodeGenerator) -> None:
    Table(
        "simple_items",
        generator.metadata,
        Column("id", INTEGER, primary_key=True),
        Column("container_id1", INTEGER),
        Column("container_id2", INTEGER),
        ForeignKeyConstraint(
            ["container_id1", "container_id2"],
            ["simple_containers.id1", "simple_containers.id2"],
            ondelete="CASCADE",
            onupdate="CASCADE",
        ),
    )
    Table(
        "simple_containers",
        generator.metadata,
        Column("id1", INTEGER, primary_key=True),
        Column("id2", INTEGER, primary_key=True),
    )

    validate_code(
        generator.generate(),
        """\
from typing import Optional

from sqlalchemy import ForeignKeyConstraint, Integer
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

class Base(DeclarativeBase):
    pass


class SimpleContainers(Base):
    __tablename__ = 'simple_containers'

    id1: Mapped[int] = mapped_column(Integer, primary_key=True)
    id2: Mapped[int] = mapped_column(Integer, primary_key=True)

    simple_items: Mapped[list['SimpleItems']] = relationship('SimpleItems', \
back_populates='simple_containers')


class SimpleItems(Base):
    __tablename__ = 'simple_items'
    __table_args__ = (
        ForeignKeyConstraint(['container_id1', 'container_id2'], \
['simple_containers.id1', 'simple_containers.id2'], ondelete='CASCADE', \
onupdate='CASCADE'),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    container_id1: Mapped[Optional[int]] = mapped_column(Integer)
    container_id2: Mapped[Optional[int]] = mapped_column(Integer)

    simple_containers: Mapped[Optional['SimpleContainers']] = relationship('SimpleContainers', \
back_populates='simple_items')
        """,
    )


def test_onetomany_multiref(generator: CodeGenerator) -> None:
    Table(
        "simple_items",
        generator.metadata,
        Column("id", INTEGER, primary_key=True),
        Column("parent_container_id", INTEGER),
        Column("top_container_id", INTEGER, nullable=False),
        ForeignKeyConstraint(["parent_container_id"], ["simple_containers.id"]),
        ForeignKeyConstraint(["top_container_id"], ["simple_containers.id"]),
    )
    Table(
        "simple_containers",
        generator.metadata,
        Column("id", INTEGER, primary_key=True),
    )

    validate_code(
        generator.generate(),
        """\
from typing import Optional

from sqlalchemy import ForeignKey, Integer
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

class Base(DeclarativeBase):
    pass


class SimpleContainers(Base):
    __tablename__ = 'simple_containers'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    simple_items: Mapped[list['SimpleItems']] = relationship('SimpleItems', \
foreign_keys='[SimpleItems.parent_container_id]', back_populates='parent_container')
    simple_items_: Mapped[list['SimpleItems']] = relationship('SimpleItems', \
foreign_keys='[SimpleItems.top_container_id]', back_populates='top_container')


class SimpleItems(Base):
    __tablename__ = 'simple_items'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    top_container_id: Mapped[int] = \
mapped_column(ForeignKey('simple_containers.id'))
    parent_container_id: Mapped[Optional[int]] = \
mapped_column(ForeignKey('simple_containers.id'))

    parent_container: Mapped[Optional['SimpleContainers']] = relationship('SimpleContainers', \
foreign_keys=[parent_container_id], back_populates='simple_items')
    top_container: Mapped['SimpleContainers'] = relationship('SimpleContainers', \
foreign_keys=[top_container_id], back_populates='simple_items_')
        """,
    )


def test_onetoone(generator: CodeGenerator) -> None:
    Table(
        "simple_items",
        generator.metadata,
        Column("id", INTEGER, primary_key=True),
        Column("other_item_id", INTEGER),
        ForeignKeyConstraint(["other_item_id"], ["other_items.id"]),
        UniqueConstraint("other_item_id"),
    )
    Table(
        "other_items",
        generator.metadata,
        Column("id", INTEGER, primary_key=True),
    )

    validate_code(
        generator.generate(),
        """\
from typing import Optional

from sqlalchemy import ForeignKey, Integer
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

class Base(DeclarativeBase):
    pass


class OtherItems(Base):
    __tablename__ = 'other_items'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    simple_items: Mapped[Optional['SimpleItems']] = relationship('SimpleItems', uselist=False, \
back_populates='other_item')


class SimpleItems(Base):
    __tablename__ = 'simple_items'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    other_item_id: Mapped[Optional[int]] = \
mapped_column(ForeignKey('other_items.id'), unique=True)

    other_item: Mapped[Optional['OtherItems']] = relationship('OtherItems', \
back_populates='simple_items')
        """,
    )


def test_onetomany_noinflect(generator: CodeGenerator) -> None:
    Table(
        "oglkrogk",
        generator.metadata,
        Column("id", INTEGER, primary_key=True),
        Column("fehwiuhfiwID", INTEGER),
        ForeignKeyConstraint(["fehwiuhfiwID"], ["fehwiuhfiw.id"]),
    )
    Table("fehwiuhfiw", generator.metadata, Column("id", INTEGER, primary_key=True))

    validate_code(
        generator.generate(),
        """\
from typing import Optional

from sqlalchemy import ForeignKey, Integer
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

class Base(DeclarativeBase):
    pass


class Fehwiuhfiw(Base):
    __tablename__ = 'fehwiuhfiw'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    oglkrogk: Mapped[list['Oglkrogk']] = relationship('Oglkrogk', \
back_populates='fehwiuhfiw')


class Oglkrogk(Base):
    __tablename__ = 'oglkrogk'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    fehwiuhfiwID: Mapped[Optional[int]] = mapped_column(ForeignKey('fehwiuhfiw.id'))

    fehwiuhfiw: Mapped[Optional['Fehwiuhfiw']] = \
relationship('Fehwiuhfiw', back_populates='oglkrogk')
        """,
    )


def test_onetomany_conflicting_column(generator: CodeGenerator) -> None:
    Table(
        "simple_items",
        generator.metadata,
        Column("id", INTEGER, primary_key=True),
        Column("container_id", INTEGER),
        ForeignKeyConstraint(["container_id"], ["simple_containers.id"]),
    )
    Table(
        "simple_containers",
        generator.metadata,
        Column("id", INTEGER, primary_key=True),
        Column("relationship", Text),
    )

    validate_code(
        generator.generate(),
        """\
from typing import Optional

from sqlalchemy import ForeignKey, Integer, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

class Base(DeclarativeBase):
    pass


class SimpleContainers(Base):
    __tablename__ = 'simple_containers'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    relationship_: Mapped[Optional[str]] = mapped_column('relationship', Text)

    simple_items: Mapped[list['SimpleItems']] = relationship('SimpleItems', \
back_populates='container')


class SimpleItems(Base):
    __tablename__ = 'simple_items'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    container_id: Mapped[Optional[int]] = \
mapped_column(ForeignKey('simple_containers.id'))

    container: Mapped[Optional['SimpleContainers']] = relationship('SimpleContainers', \
back_populates='simple_items')
        """,
    )


def test_onetomany_conflicting_relationship(generator: CodeGenerator) -> None:
    Table(
        "simple_items",
        generator.metadata,
        Column("id", INTEGER, primary_key=True),
        Column("relationship_id", INTEGER),
        ForeignKeyConstraint(["relationship_id"], ["relationship.id"]),
    )
    Table("relationship", generator.metadata, Column("id", INTEGER, primary_key=True))

    validate_code(
        generator.generate(),
        """\
from typing import Optional

from sqlalchemy import ForeignKey, Integer
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

class Base(DeclarativeBase):
    pass


class Relationship(Base):
    __tablename__ = 'relationship'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    simple_items: Mapped[list['SimpleItems']] = relationship('SimpleItems', \
back_populates='relationship_')


class SimpleItems(Base):
    __tablename__ = 'simple_items'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    relationship_id: Mapped[Optional[int]] = \
mapped_column(ForeignKey('relationship.id'))

    relationship_: Mapped[Optional['Relationship']] = relationship('Relationship', \
back_populates='simple_items')
        """,
    )


@pytest.mark.parametrize("generator", [["nobidi"]], indirect=True)
def test_manytoone_nobidi(generator: CodeGenerator) -> None:
    Table(
        "simple_items",
        generator.metadata,
        Column("id", INTEGER, primary_key=True),
        Column("container_id", INTEGER),
        ForeignKeyConstraint(["container_id"], ["simple_containers.id"]),
    )
    Table(
        "simple_containers",
        generator.metadata,
        Column("id", INTEGER, primary_key=True),
    )

    validate_code(
        generator.generate(),
        """\
from typing import Optional

from sqlalchemy import ForeignKey, Integer
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

class Base(DeclarativeBase):
    pass


class SimpleContainers(Base):
    __tablename__ = 'simple_containers'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)


class SimpleItems(Base):
    __tablename__ = 'simple_items'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    container_id: Mapped[Optional[int]] = \
mapped_column(ForeignKey('simple_containers.id'))

    container: Mapped[Optional['SimpleContainers']] = relationship('SimpleContainers')
""",
    )


def test_manytomany(generator: CodeGenerator) -> None:
    Table("left_table", generator.metadata, Column("id", INTEGER, primary_key=True))
    Table(
        "right_table",
        generator.metadata,
        Column("id", INTEGER, primary_key=True),
    )
    Table(
        "association_table",
        generator.metadata,
        Column("left_id", INTEGER),
        Column("right_id", INTEGER),
        ForeignKeyConstraint(["left_id"], ["left_table.id"]),
        ForeignKeyConstraint(["right_id"], ["right_table.id"]),
    )

    validate_code(
        generator.generate(),
        """\
from sqlalchemy import Column, ForeignKey, Integer, Table
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

class Base(DeclarativeBase):
    pass


class LeftTable(Base):
    __tablename__ = 'left_table'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    right: Mapped[list['RightTable']] = relationship('RightTable', \
secondary='association_table', back_populates='left')


class RightTable(Base):
    __tablename__ = 'right_table'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    left: Mapped[list['LeftTable']] = relationship('LeftTable', \
secondary='association_table', back_populates='right')


t_association_table = Table(
    'association_table', Base.metadata,
    Column('left_id', ForeignKey('left_table.id')),
    Column('right_id', ForeignKey('right_table.id'))
)
        """,
    )


@pytest.mark.parametrize("generator", [["nobidi"]], indirect=True)
def test_manytomany_nobidi(generator: CodeGenerator) -> None:
    Table("simple_items", generator.metadata, Column("id", INTEGER, primary_key=True))
    Table(
        "simple_containers",
        generator.metadata,
        Column("id", INTEGER, primary_key=True),
    )
    Table(
        "container_items",
        generator.metadata,
        Column("item_id", INTEGER),
        Column("container_id", INTEGER),
        ForeignKeyConstraint(["item_id"], ["simple_items.id"]),
        ForeignKeyConstraint(["container_id"], ["simple_containers.id"]),
    )

    validate_code(
        generator.generate(),
        """\
from sqlalchemy import Column, ForeignKey, Integer, Table
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

class Base(DeclarativeBase):
    pass


class SimpleContainers(Base):
    __tablename__ = 'simple_containers'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    item: Mapped[list['SimpleItems']] = relationship('SimpleItems', \
secondary='container_items')


class SimpleItems(Base):
    __tablename__ = 'simple_items'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)


t_container_items = Table(
    'container_items', Base.metadata,
    Column('item_id', ForeignKey('simple_items.id')),
    Column('container_id', ForeignKey('simple_containers.id'))
)
            """,
    )


def test_manytomany_selfref(generator: CodeGenerator) -> None:
    Table("simple_items", generator.metadata, Column("id", INTEGER, primary_key=True))
    Table(
        "child_items",
        generator.metadata,
        Column("parent_id", INTEGER),
        Column("child_id", INTEGER),
        ForeignKeyConstraint(["parent_id"], ["simple_items.id"]),
        ForeignKeyConstraint(["child_id"], ["simple_items.id"]),
        schema="otherschema",
    )

    validate_code(
        generator.generate(),
        """\
from sqlalchemy import Column, ForeignKey, Integer, Table
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

class Base(DeclarativeBase):
    pass


class SimpleItems(Base):
    __tablename__ = 'simple_items'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    parent: Mapped[list['SimpleItems']] = relationship('SimpleItems', \
secondary='otherschema.child_items', primaryjoin=lambda: SimpleItems.id \
== t_child_items.c.child_id, \
secondaryjoin=lambda: SimpleItems.id == \
t_child_items.c.parent_id, back_populates='child')
    child: Mapped[list['SimpleItems']] = \
relationship('SimpleItems', secondary='otherschema.child_items', \
primaryjoin=lambda: SimpleItems.id == t_child_items.c.parent_id, \
secondaryjoin=lambda: SimpleItems.id == t_child_items.c.child_id, \
back_populates='parent')


t_child_items = Table(
    'child_items', Base.metadata,
    Column('parent_id', ForeignKey('simple_items.id')),
    Column('child_id', ForeignKey('simple_items.id')),
    schema='otherschema'
)
        """,
    )


def test_manytomany_composite(generator: CodeGenerator) -> None:
    Table(
        "simple_items",
        generator.metadata,
        Column("id1", INTEGER, primary_key=True),
        Column("id2", INTEGER, primary_key=True),
    )
    Table(
        "simple_containers",
        generator.metadata,
        Column("id1", INTEGER, primary_key=True),
        Column("id2", INTEGER, primary_key=True),
    )
    Table(
        "container_items",
        generator.metadata,
        Column("item_id1", INTEGER),
        Column("item_id2", INTEGER),
        Column("container_id1", INTEGER),
        Column("container_id2", INTEGER),
        ForeignKeyConstraint(
            ["item_id1", "item_id2"], ["simple_items.id1", "simple_items.id2"]
        ),
        ForeignKeyConstraint(
            ["container_id1", "container_id2"],
            ["simple_containers.id1", "simple_containers.id2"],
        ),
    )

    validate_code(
        generator.generate(),
        """\
from sqlalchemy import Column, ForeignKeyConstraint, Integer, Table
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

class Base(DeclarativeBase):
    pass


class SimpleContainers(Base):
    __tablename__ = 'simple_containers'

    id1: Mapped[int] = mapped_column(Integer, primary_key=True)
    id2: Mapped[int] = mapped_column(Integer, primary_key=True)

    simple_items: Mapped[list['SimpleItems']] = relationship('SimpleItems', \
secondary='container_items', back_populates='simple_containers')


class SimpleItems(Base):
    __tablename__ = 'simple_items'

    id1: Mapped[int] = mapped_column(Integer, primary_key=True)
    id2: Mapped[int] = mapped_column(Integer, primary_key=True)

    simple_containers: Mapped[list['SimpleContainers']] = \
relationship('SimpleContainers', secondary='container_items', \
back_populates='simple_items')


t_container_items = Table(
    'container_items', Base.metadata,
    Column('item_id1', Integer),
    Column('item_id2', Integer),
    Column('container_id1', Integer),
    Column('container_id2', Integer),
    ForeignKeyConstraint(['container_id1', 'container_id2'], \
['simple_containers.id1', 'simple_containers.id2']),
    ForeignKeyConstraint(['item_id1', 'item_id2'], \
['simple_items.id1', 'simple_items.id2'])
)
        """,
    )


def test_joined_inheritance(generator: CodeGenerator) -> None:
    Table(
        "simple_sub_items",
        generator.metadata,
        Column("simple_items_id", INTEGER, primary_key=True),
        Column("data3", INTEGER),
        ForeignKeyConstraint(["simple_items_id"], ["simple_items.super_item_id"]),
    )
    Table(
        "simple_super_items",
        generator.metadata,
        Column("id", INTEGER, primary_key=True),
        Column("data1", INTEGER),
    )
    Table(
        "simple_items",
        generator.metadata,
        Column("super_item_id", INTEGER, primary_key=True),
        Column("data2", INTEGER),
        ForeignKeyConstraint(["super_item_id"], ["simple_super_items.id"]),
    )

    validate_code(
        generator.generate(),
        """\
from typing import Optional

from sqlalchemy import ForeignKey, Integer
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

class Base(DeclarativeBase):
    pass


class SimpleSuperItems(Base):
    __tablename__ = 'simple_super_items'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    data1: Mapped[Optional[int]] = mapped_column(Integer)


class SimpleItems(SimpleSuperItems):
    __tablename__ = 'simple_items'

    super_item_id: Mapped[int] = mapped_column(ForeignKey('simple_super_items.id'), \
primary_key=True)
    data2: Mapped[Optional[int]] = mapped_column(Integer)


class SimpleSubItems(SimpleItems):
    __tablename__ = 'simple_sub_items'

    simple_items_id: Mapped[int] = \
mapped_column(ForeignKey('simple_items.super_item_id'), primary_key=True)
    data3: Mapped[Optional[int]] = mapped_column(Integer)
        """,
    )


def test_joined_inheritance_same_table_name(generator: CodeGenerator) -> None:
    Table(
        "simple",
        generator.metadata,
        Column("id", INTEGER, primary_key=True),
    )
    Table(
        "simple",
        generator.metadata,
        Column("id", INTEGER, ForeignKey("simple.id"), primary_key=True),
        schema="altschema",
    )

    validate_code(
        generator.generate(),
        """\
    from sqlalchemy import ForeignKey, Integer
    from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

    class Base(DeclarativeBase):
        pass


    class Simple(Base):
        __tablename__ = 'simple'

        id: Mapped[int] = mapped_column(Integer, primary_key=True)


    class Simple_(Simple):
        __tablename__ = 'simple'
        __table_args__ = {'schema': 'altschema'}

        id: Mapped[int] = mapped_column(ForeignKey('simple.id'), primary_key=True)
        """,
    )


@pytest.mark.parametrize("generator", [["use_inflect"]], indirect=True)
def test_use_inflect(generator: CodeGenerator) -> None:
    Table("simple_items", generator.metadata, Column("id", INTEGER, primary_key=True))

    Table("singular", generator.metadata, Column("id", INTEGER, primary_key=True))

    validate_code(
        generator.generate(),
        """\
from sqlalchemy import Integer
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

class Base(DeclarativeBase):
    pass


class SimpleItem(Base):
    __tablename__ = 'simple_items'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)


class Singular(Base):
    __tablename__ = 'singular'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
        """,
    )


@pytest.mark.parametrize("generator", [["use_inflect"]], indirect=True)
@pytest.mark.parametrize(
    argnames=("table_name", "class_name", "relationship_name"),
    argvalues=[
        ("manufacturers", "manufacturer", "manufacturer"),
        ("statuses", "status", "status"),
        ("studies", "study", "study"),
        ("moose", "moose", "moose"),
    ],
    ids=[
        "test_inflect_manufacturer",
        "test_inflect_status",
        "test_inflect_study",
        "test_inflect_moose",
    ],
)
def test_use_inflect_plural(
    generator: CodeGenerator,
    table_name: str,
    class_name: str,
    relationship_name: str,
) -> None:
    Table(
        "simple_items",
        generator.metadata,
        Column("id", INTEGER, primary_key=True),
        Column(f"{relationship_name}_id", INTEGER),
        ForeignKeyConstraint([f"{relationship_name}_id"], [f"{table_name}.id"]),
        UniqueConstraint(f"{relationship_name}_id"),
    )
    Table(table_name, generator.metadata, Column("id", INTEGER, primary_key=True))

    validate_code(
        generator.generate(),
        f"""\
from typing import Optional

from sqlalchemy import ForeignKey, Integer
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

class Base(DeclarativeBase):
    pass


class {class_name.capitalize()}(Base):
    __tablename__ = '{table_name}'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    simple_item: Mapped[Optional['SimpleItem']] = relationship('SimpleItem', uselist=False, \
back_populates='{relationship_name}')


class SimpleItem(Base):
    __tablename__ = 'simple_items'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    {relationship_name}_id: Mapped[Optional[int]] = \
mapped_column(ForeignKey('{table_name}.id'), unique=True)

    {relationship_name}: Mapped[Optional['{class_name.capitalize()}']] = \
relationship('{class_name.capitalize()}', back_populates='simple_item')
        """,
    )


@pytest.mark.parametrize("generator", [["use_inflect"]], indirect=True)
def test_use_inflect_plural_double_pluralize(generator: CodeGenerator) -> None:
    Table(
        "users",
        generator.metadata,
        Column("users_id", INTEGER),
        Column("groups_id", INTEGER),
        ForeignKeyConstraint(
            ["groups_id"], ["groups.groups_id"], name="fk_users_groups_id"
        ),
        PrimaryKeyConstraint("users_id", name="users_pkey"),
    )

    Table(
        "groups",
        generator.metadata,
        Column("groups_id", INTEGER),
        Column("group_name", Text(50), nullable=False),
        PrimaryKeyConstraint("groups_id", name="groups_pkey"),
    )

    validate_code(
        generator.generate(),
        """\
from typing import Optional

from sqlalchemy import ForeignKeyConstraint, Integer, PrimaryKeyConstraint, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

class Base(DeclarativeBase):
    pass


class Group(Base):
    __tablename__ = 'groups'
    __table_args__ = (
        PrimaryKeyConstraint('groups_id', name='groups_pkey'),
    )

    groups_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    group_name: Mapped[str] = mapped_column(Text(50))

    users: Mapped[list['User']] = relationship('User', back_populates='group')


class User(Base):
    __tablename__ = 'users'
    __table_args__ = (
        ForeignKeyConstraint(['groups_id'], ['groups.groups_id'], name='fk_users_groups_id'),
        PrimaryKeyConstraint('users_id', name='users_pkey')
    )

    users_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    groups_id: Mapped[Optional[int]] = mapped_column(Integer)

    group: Mapped[Optional['Group']] = relationship('Group', back_populates='users')
    """,
    )


def test_table_kwargs(generator: CodeGenerator) -> None:
    Table(
        "simple_items",
        generator.metadata,
        Column("id", INTEGER, primary_key=True),
        schema="testschema",
    )

    validate_code(
        generator.generate(),
        """\
from sqlalchemy import Integer
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

class Base(DeclarativeBase):
    pass


class SimpleItems(Base):
    __tablename__ = 'simple_items'
    __table_args__ = {'schema': 'testschema'}

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
        """,
    )


def test_table_args_kwargs(generator: CodeGenerator) -> None:
    simple_items = Table(
        "simple_items",
        generator.metadata,
        Column("id", INTEGER, primary_key=True),
        Column("name", VARCHAR),
        schema="testschema",
    )
    simple_items.indexes.add(Index("testidx", simple_items.c.id, simple_items.c.name))

    validate_code(
        generator.generate(),
        """\
from typing import Optional

from sqlalchemy import Index, Integer, String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

class Base(DeclarativeBase):
    pass


class SimpleItems(Base):
    __tablename__ = 'simple_items'
    __table_args__ = (
        Index('testidx', 'id', 'name'),
        {'schema': 'testschema'}
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[Optional[str]] = mapped_column(String)
        """,
    )


def test_foreign_key_schema(generator: CodeGenerator) -> None:
    Table(
        "simple_items",
        generator.metadata,
        Column("id", INTEGER, primary_key=True),
        Column("other_item_id", INTEGER),
        ForeignKeyConstraint(["other_item_id"], ["otherschema.other_items.id"]),
    )
    Table(
        "other_items",
        generator.metadata,
        Column("id", INTEGER, primary_key=True),
        schema="otherschema",
    )

    validate_code(
        generator.generate(),
        """\
from typing import Optional

from sqlalchemy import ForeignKey, Integer
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

class Base(DeclarativeBase):
    pass


class OtherItems(Base):
    __tablename__ = 'other_items'
    __table_args__ = {'schema': 'otherschema'}

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    simple_items: Mapped[list['SimpleItems']] = relationship('SimpleItems', \
back_populates='other_item')


class SimpleItems(Base):
    __tablename__ = 'simple_items'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    other_item_id: Mapped[Optional[int]] = \
mapped_column(ForeignKey('otherschema.other_items.id'))

    other_item: Mapped[Optional['OtherItems']] = relationship('OtherItems', \
back_populates='simple_items')
        """,
    )


def test_invalid_attribute_names(generator: CodeGenerator) -> None:
    Table(
        "simple-items",
        generator.metadata,
        Column("id-test", INTEGER, primary_key=True),
        Column("4test", INTEGER),
        Column("_4test", INTEGER),
        Column("def", INTEGER),
    )

    validate_code(
        generator.generate(),
        """\
from typing import Optional

from sqlalchemy import Integer
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

class Base(DeclarativeBase):
    pass


class SimpleItems(Base):
    __tablename__ = 'simple-items'

    id_test: Mapped[int] = mapped_column('id-test', Integer, primary_key=True)
    _4test: Mapped[Optional[int]] = mapped_column('4test', Integer)
    _4test_: Mapped[Optional[int]] = mapped_column('_4test', Integer)
    def_: Mapped[Optional[int]] = mapped_column('def', Integer)
        """,
    )


def test_pascal(generator: CodeGenerator) -> None:
    Table(
        "CustomerAPIPreference",
        generator.metadata,
        Column("id", INTEGER, primary_key=True),
    )

    validate_code(
        generator.generate(),
        """\
from sqlalchemy import Integer
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

class Base(DeclarativeBase):
    pass


class CustomerAPIPreference(Base):
    __tablename__ = 'CustomerAPIPreference'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
        """,
    )


def test_underscore(generator: CodeGenerator) -> None:
    Table(
        "customer_api_preference",
        generator.metadata,
        Column("id", INTEGER, primary_key=True),
    )

    validate_code(
        generator.generate(),
        """\
from sqlalchemy import Integer
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

class Base(DeclarativeBase):
    pass


class CustomerApiPreference(Base):
    __tablename__ = 'customer_api_preference'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
        """,
    )


def test_pascal_underscore(generator: CodeGenerator) -> None:
    Table(
        "customer_API_Preference",
        generator.metadata,
        Column("id", INTEGER, primary_key=True),
    )

    validate_code(
        generator.generate(),
        """\
from sqlalchemy import Integer
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

class Base(DeclarativeBase):
    pass


class CustomerAPIPreference(Base):
    __tablename__ = 'customer_API_Preference'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
        """,
    )


def test_pascal_multiple_underscore(generator: CodeGenerator) -> None:
    Table(
        "customer_API__Preference",
        generator.metadata,
        Column("id", INTEGER, primary_key=True),
    )

    validate_code(
        generator.generate(),
        """\
from sqlalchemy import Integer
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

class Base(DeclarativeBase):
    pass


class CustomerAPIPreference(Base):
    __tablename__ = 'customer_API__Preference'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
        """,
    )


@pytest.mark.parametrize(
    "generator, nocomments",
    [([], False), (["nocomments"], True)],
    indirect=["generator"],
)
def test_column_comment(generator: CodeGenerator, nocomments: bool) -> None:
    Table(
        "simple",
        generator.metadata,
        Column("id", INTEGER, primary_key=True, comment="this is a 'comment'"),
    )

    comment_part = "" if nocomments else ", comment=\"this is a 'comment'\""
    validate_code(
        generator.generate(),
        f"""\
from sqlalchemy import Integer
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

class Base(DeclarativeBase):
    pass


class Simple(Base):
    __tablename__ = 'simple'

    id: Mapped[int] = mapped_column(Integer, primary_key=True{comment_part})
""",
    )


def test_table_comment(generator: CodeGenerator) -> None:
    Table(
        "simple",
        generator.metadata,
        Column("id", INTEGER, primary_key=True),
        comment="this is a 'comment'",
    )

    validate_code(
        generator.generate(),
        """\
from sqlalchemy import Integer
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

class Base(DeclarativeBase):
    pass


class Simple(Base):
    __tablename__ = 'simple'
    __table_args__ = {'comment': "this is a 'comment'"}

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
""",
    )


def test_metadata_column(generator: CodeGenerator) -> None:
    Table(
        "simple",
        generator.metadata,
        Column("id", INTEGER, primary_key=True),
        Column("metadata", VARCHAR),
    )

    validate_code(
        generator.generate(),
        """\
from typing import Optional

from sqlalchemy import Integer, String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

class Base(DeclarativeBase):
    pass


class Simple(Base):
    __tablename__ = 'simple'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    metadata_: Mapped[Optional[str]] = mapped_column('metadata', String)
""",
    )


def test_invalid_variable_name_from_column(generator: CodeGenerator) -> None:
    Table(
        "simple",
        generator.metadata,
        Column(" id ", INTEGER, primary_key=True),
    )

    validate_code(
        generator.generate(),
        """\
from sqlalchemy import Integer
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

class Base(DeclarativeBase):
    pass


class Simple(Base):
    __tablename__ = 'simple'

    id: Mapped[int] = mapped_column(' id ', Integer, primary_key=True)
""",
    )


def test_only_tables(generator: CodeGenerator) -> None:
    Table("simple", generator.metadata, Column("id", INTEGER))

    validate_code(
        generator.generate(),
        """\
from sqlalchemy import Column, Integer, MetaData, Table

metadata = MetaData()


t_simple = Table(
    'simple', metadata,
    Column('id', Integer)
)
            """,
    )


def test_named_constraints(generator: CodeGenerator) -> None:
    Table(
        "simple",
        generator.metadata,
        Column("id", INTEGER),
        Column("text", VARCHAR),
        CheckConstraint("id > 0", name="checktest"),
        PrimaryKeyConstraint("id", name="primarytest"),
        UniqueConstraint("text", name="uniquetest"),
    )

    validate_code(
        generator.generate(),
        """\
from typing import Optional

from sqlalchemy import CheckConstraint, Integer, PrimaryKeyConstraint, \
String, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

class Base(DeclarativeBase):
    pass


class Simple(Base):
    __tablename__ = 'simple'
    __table_args__ = (
        CheckConstraint('id > 0', name='checktest'),
        PrimaryKeyConstraint('id', name='primarytest'),
        UniqueConstraint('text', name='uniquetest')
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    text: Mapped[Optional[str]] = mapped_column(String)
""",
    )


def test_named_foreign_key_constraints(generator: CodeGenerator) -> None:
    Table(
        "simple_items",
        generator.metadata,
        Column("id", INTEGER, primary_key=True),
        Column("container_id", INTEGER),
        ForeignKeyConstraint(
            ["container_id"], ["simple_containers.id"], name="foreignkeytest"
        ),
    )
    Table(
        "simple_containers",
        generator.metadata,
        Column("id", INTEGER, primary_key=True),
    )

    validate_code(
        generator.generate(),
        """\
from typing import Optional

from sqlalchemy import ForeignKeyConstraint, Integer
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

class Base(DeclarativeBase):
    pass


class SimpleContainers(Base):
    __tablename__ = 'simple_containers'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    simple_items: Mapped[list['SimpleItems']] = relationship('SimpleItems', \
back_populates='container')


class SimpleItems(Base):
    __tablename__ = 'simple_items'
    __table_args__ = (
        ForeignKeyConstraint(['container_id'], ['simple_containers.id'], \
name='foreignkeytest'),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    container_id: Mapped[Optional[int]] = mapped_column(Integer)

    container: Mapped[Optional['SimpleContainers']] = relationship('SimpleContainers', \
back_populates='simple_items')
""",
    )


# @pytest.mark.xfail(strict=True)
def test_colname_import_conflict(generator: CodeGenerator) -> None:
    Table(
        "simple",
        generator.metadata,
        Column("id", INTEGER, primary_key=True),
        Column("text", VARCHAR),
        Column("textwithdefault", VARCHAR, server_default=text("'test'")),
    )

    validate_code(
        generator.generate(),
        """\
from typing import Optional

from sqlalchemy import Integer, String, text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

class Base(DeclarativeBase):
    pass


class Simple(Base):
    __tablename__ = 'simple'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    text_: Mapped[Optional[str]] = mapped_column('text', String)
    textwithdefault: Mapped[Optional[str]] = mapped_column(String, \
server_default=text("'test'"))
""",
    )


def test_table_with_arrays(generator: CodeGenerator) -> None:
    Table(
        "with_items",
        generator.metadata,
        Column("id", INTEGER, primary_key=True),
        Column("int_items_not_optional", ARRAY(INTEGER()), nullable=False),
        Column("str_matrix", ARRAY(VARCHAR(), dimensions=2)),
    )

    validate_code(
        generator.generate(),
        """\
from typing import Optional

from sqlalchemy import ARRAY, INTEGER, Integer, VARCHAR
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

class Base(DeclarativeBase):
    pass


class WithItems(Base):
    __tablename__ = 'with_items'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    int_items_not_optional: Mapped[list[int]] = mapped_column(ARRAY(INTEGER()))
    str_matrix: Mapped[Optional[list[list[str]]]] = mapped_column(ARRAY(VARCHAR(), dimensions=2))
""",
    )


@pytest.mark.parametrize("engine", ["postgresql"], indirect=["engine"])
def test_domain_json(generator: CodeGenerator) -> None:
    Table(
        "test_domain_json",
        generator.metadata,
        Column("id", BIGINT, primary_key=True),
        Column(
            "foo",
            postgresql.DOMAIN(
                "domain_json",
                JSON,
                not_null=False,
            ),
            nullable=True,
        ),
    )

    validate_code(
        generator.generate(),
        """\
from typing import Optional

from sqlalchemy import BigInteger
from sqlalchemy.dialects.postgresql import DOMAIN, JSON
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

class Base(DeclarativeBase):
    pass


class TestDomainJson(Base):
    __tablename__ = 'test_domain_json'

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    foo: Mapped[Optional[dict]] = mapped_column(DOMAIN('domain_json', JSON(), not_null=False))
""",
    )


@pytest.mark.parametrize(
    "domain_type",
    [JSONB, JSON],
)
def test_domain_non_default_json(
    generator: CodeGenerator,
    domain_type: type[JSON] | type[JSONB],
) -> None:
    Table(
        "test_domain_json",
        generator.metadata,
        Column("id", BIGINT, primary_key=True),
        Column(
            "foo",
            postgresql.DOMAIN(
                "domain_json",
                domain_type(astext_type=Text(128)),
                not_null=False,
            ),
            nullable=True,
        ),
    )

    validate_code(
        generator.generate(),
        f"""\
from typing import Optional

from sqlalchemy import BigInteger, Text
from sqlalchemy.dialects.postgresql import DOMAIN, {domain_type.__name__}
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

class Base(DeclarativeBase):
    pass


class TestDomainJson(Base):
    __tablename__ = 'test_domain_json'

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    foo: Mapped[Optional[dict]] = mapped_column(DOMAIN('domain_json', {domain_type.__name__}(astext_type=Text(length=128)), not_null=False))
""",
    )
