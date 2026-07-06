-- CRS transformation can introduce tiny self-intersections. Repair only monitoring geometry.
UPDATE analysis.zone_snapshot
SET geom = ST_Multi(ST_CollectionExtract(ST_MakeValid(geom), 3))::geometry(MultiPolygon, 5179)
WHERE NOT ST_IsValid(geom);

UPDATE analysis.zone_current
SET geom = ST_Multi(ST_CollectionExtract(ST_MakeValid(geom), 3))::geometry(MultiPolygon, 5179)
WHERE NOT ST_IsValid(geom);
