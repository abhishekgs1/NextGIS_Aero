INSERT INTO ct (
    id,
    geom,
    fld_i,
    fld_t,
    fld_d
)
VALUES
    (nextval('id_seqt'), :geom, :fld_1, :fld_2, :fld_3)
RETURNING ct.id;
