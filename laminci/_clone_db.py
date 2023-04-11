# This starts out with https://stackoverflow.com/questions/70392123
import sqlalchemy as sa
from sqlalchemy import MetaData, create_engine, func, select


def clone_schema(
    schema, src_conn, src_metadata, tgt_conn, tgt_metadata, tgt_engine, n_rows: int
):
    n_rows_test = n_rows
    # !!! switch off foreign key integrity !!!
    # this is needed because we haven't yet figured out a way to clone connected records
    # might never be needed because we don't want to apply this to large databases
    if src_conn.dialect.name == "postgresql":
        tgt_conn.execute(sa.sql.text("SET session_replication_role = replica;"))

    # create all tables in target database
    for table in src_metadata.sorted_tables:
        if not sa.inspect(tgt_engine).has_table(table.name, table.schema):
            table.create(bind=tgt_engine)
    # refresh metadata before copying data
    tgt_metadata.clear()
    tgt_metadata.reflect(bind=tgt_engine, schema=schema)

    # copy data
    print("Cloning: ", end="")
    for table in tgt_metadata.sorted_tables:
        if table.schema != schema:
            continue
        src_table = src_metadata.tables[f"{schema}.{table.name}"]
        n_rows = -1  # indicates no rows
        if len(list(src_table.primary_key)) > 0:
            pk_col = getattr(src_table.c, list(src_table.primary_key)[0].name)
            n_rows = int(
                src_conn.execute(
                    select([func.count(pk_col)]).select_from(src_table)
                ).scalar()
            )
        offset = max(n_rows - n_rows_test, 0)
        print(f"{table.name} ({n_rows-offset}/{n_rows})", end=", ")
        rows = src_conn.execute(src_table.select().offset(offset))
        values = [row._asdict() for index, row in enumerate(rows)]
        if len(values) > 0:
            tgt_conn.execute(table.insert(), values)
            tgt_conn.commit()


# fixating the number of rows is not a good proxy for getting
# a connected slice of data... not sure whether something better exists
def clone_db(
    *,
    source_db: str,
    target_db: str,
    n_rows: int = 10000,
) -> str:
    """Clone from current instance to a test instance.

    Args:
        source_db: Connection string of source database.
        target_db: Connection string of target database.
        n_rows: Number of rows to clone.
    """
    assert source_db != target_db

    src_engine = create_engine(source_db, future=True)
    src_metadata = MetaData()
    tgt_engine = create_engine(target_db, future=True)
    tgt_metadata = MetaData()
    src_conn = src_engine.connect()
    src_metadata.reflect(bind=src_engine)
    tgt_conn = tgt_engine.connect()

    # create all schemas in target database
    src_schemas = src_conn.dialect.get_schema_names(src_conn)
    for schemaname in src_schemas:
        if schemaname not in tgt_conn.dialect.get_schema_names(tgt_conn):
            tgt_conn.execute(sa.schema.CreateSchema(schemaname))
        tgt_conn.commit()

    # only relevant for postgres, clean out some default schemas
    for schema in [
        "information_schema",
        "auth",
        "graphql",
        "graphql_public",
        "realtime",
        "extensions",
        "storage",
    ]:
        if schema in src_schemas:
            src_schemas.remove(schema)

    for schema in src_schemas:
        src_metadata.reflect(bind=src_engine, schema=schema)
        tgt_metadata.reflect(bind=tgt_engine, schema=schema)
        if src_engine.dialect.name != "sqlite":
            print(f"\nSchema: {schema}")
        clone_schema(
            schema, src_conn, src_metadata, tgt_conn, tgt_metadata, tgt_engine, n_rows
        )
    # print a new line
    print("")
    return target_db
