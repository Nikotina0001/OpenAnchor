from dataclasses import replace

import numpy as np
import pytest
from shapely.geometry import Point, Polygon, box

from openanchor.geometry import (contact_footprint, generate, intersection_volume,
                                 lower_outline, prism, solid, transformed)
from openanchor.settings import Settings, layer_boundaries
from openanchor.beams import beam_footprint


BED = box(0, 0, 256, 256)
LAYERS = layer_boundaries(0.2, 0.2, 3)
U_SHAPE = Polygon([(80,80),(140,80),(140,140),(125,140),
                   (125,95),(95,95),(95,140),(80,140)])


def test_facing_beams_cannot_cross_a_neighbor_to_reach_a_remote_wall():
    shape = box(90,100,110,120).union(box(114,100,134,120))
    outer = shape.buffer(15, join_style='mitre')
    wall = outer.difference(shape.buffer(5, join_style='mitre'))
    cap = outer.difference(shape.buffer(3, join_style='mitre'))
    ribs, count, corners = beam_footprint(shape, wall, cap,
                                        replace(Settings(), advanced_anchor=True))
    # The two facing midpoints have no wall before the neighboring object.
    assert count == 14
    assert corners == 8
    assert ribs.distance(shape) >= Settings().beam_model_gap


@pytest.mark.parametrize('shape', [box(100,100,120,120), U_SHAPE,
                                  Point(110,110).buffer(12,quad_segs=24),
                                  box(90,90,130,130).difference(box(100,100,120,120)),
                                  box(60,100,70,110).union(box(150,100,160,110))])
def test_advanced_beams_rise_from_bed_through_slots_and_join_cap(shape):
    model = prism(shape, 0, 10)
    normal = generate(model, Settings(), LAYERS, BED)
    settings = replace(Settings(), advanced_anchor=True)
    assembly = generate(model, settings, LAYERS, BED)
    assert assembly.report['beam_count'] > 0
    assert all(mesh.is_volume for mesh in (assembly.model,assembly.flange,assembly.anchor))
    import trimesh
    for mesh in (assembly.flange,assembly.anchor):
        native=trimesh.Trimesh(mesh.vertices.astype('float32'),mesh.faces,process=False)
        assert native.is_volume and np.all(native.area_faces>1e-12)
    assert np.array_equal(assembly.model.vertices,model.vertices)
    assert np.array_equal(assembly.model.faces,model.faces)
    assert assembly.flange.volume < normal.flange.volume
    assert assembly.anchor.volume > normal.anchor.volume
    assert intersection_volume(assembly.flange,assembly.anchor) < 1e-6
    assert intersection_volume(model,assembly.anchor) < 1e-6
    ribs = contact_footprint(assembly.anchor).difference(contact_footprint(normal.anchor))
    assert ribs.area > 0
    assert ribs.distance(lower_outline(model,1.2)) >= settings.beam_model_gap - 1e-6
    assert len(solid(assembly.anchor).decompose()) == len(solid(normal.anchor).decompose())
    assert assembly.anchor.bounds[0,2] == pytest.approx(0)


def test_square_has_diagonal_corner_and_regular_perpendicular_beams():
    assembly = generate(prism(box(100,100,120,120),0,10),
                        replace(Settings(),advanced_anchor=True),LAYERS,BED)
    assert assembly.report['corner_beam_count'] == 4
    assert assembly.report['beam_count'] >= 8


def test_mirrored_rotated_sloped_geometry_keeps_source_and_clearance():
    import trimesh
    model = trimesh.creation.box([20,20,10])
    model.vertices[model.vertices[:,2]>0,:2] *= 1.3
    model.apply_translation([110,110,5])
    matrix = trimesh.transformations.rotation_matrix(.4,[0,0,1],point=[110,110,0])
    mirror = np.diag([-1.,1.,1.,1.]);mirror[0,3]=220
    model = transformed(model,matrix@mirror)
    assembly = generate(model,replace(Settings(),advanced_anchor=True),LAYERS,BED)
    assert np.array_equal(assembly.model.vertices,model.vertices)
    assert intersection_volume(model,assembly.anchor)<1e-6
    assert intersection_volume(assembly.flange,assembly.anchor)<1e-6


@pytest.mark.parametrize('values', [
    {'advanced_anchor':1}, {'beam_width':float('nan')}, {'beam_spacing':0},
    {'beam_model_gap':-1}, {'beam_width':0.4},
    {'beam_spacing':2,'beam_width':2}, {'beam_model_gap':0.2},
])
def test_invalid_beam_settings_rejected(values):
    with pytest.raises(ValueError):
        replace(Settings(),**dict({'advanced_anchor':True},**values)).validate(2)


def test_exact_decimal_clearance_boundary_and_nonzero_slot_gap():
    settings=replace(Settings(),advanced_anchor=True,gap=0.1,beam_model_gap=0.6)
    settings.validate(2)
    model=prism(box(100,100,120,120),0,10)
    normal=generate(model,replace(settings,advanced_anchor=False),LAYERS,BED)
    assembly=generate(model,settings,LAYERS,BED)
    ribs=contact_footprint(assembly.anchor).difference(contact_footprint(normal.anchor))
    assert ribs.distance(contact_footprint(assembly.flange))>=0.1-1e-4
    assert intersection_volume(assembly.flange,assembly.anchor)<1e-6


def test_extreme_beam_count_is_rejected():
    with pytest.raises(ValueError,match='Too many support beams'):
        generate(prism(box(100,100,900,900),0,10),
                 replace(Settings(),advanced_anchor=True,beam_spacing=2),LAYERS,box(0,0,2000,2000))


@pytest.mark.parametrize('slope',[1.0,1.3])
@pytest.mark.parametrize('rotation',[0,0.4])
def test_zero_nominal_object_gap_handles_native_float_fit(slope,rotation):
    import trimesh
    model=trimesh.creation.box([20,20,10])
    model.vertices[model.vertices[:,2]>0,:2]*=slope
    model.apply_translation([110,110,5])
    model=transformed(model,trimesh.transformations.rotation_matrix(rotation,[0,0,1],point=[110,110,0]))
    assembly=generate(model,replace(Settings(),advanced_anchor=True,flange_object_gap=0),LAYERS,BED)
    assert np.array_equal(assembly.model.vertices,model.vertices)
    assert intersection_volume(model,assembly.flange)<1e-6
    assert assembly.report['native_fit_tolerance_mm']<=0.001
