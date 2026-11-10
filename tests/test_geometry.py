from dataclasses import replace
import numpy as np
import pytest
import trimesh
from shapely.geometry import Polygon, Point, box
from openanchor.geometry import generate, prism, contact_footprint, transformed, intersection_volume, lower_outline
from openanchor.settings import Settings, align_heights, layer_boundaries

BED = box(0, 0, 256, 256)
LAYERS = layer_boundaries(0.2, 0.2, 5)


@pytest.fixture
def model():
    return prism(box(100, 100, 120, 120), 0, 10)


def check(assembly):
    h = assembly.report['effective_flange_height_mm']
    assert assembly.model.bounds[0, 2] == pytest.approx(0)
    assert assembly.flange.bounds[0, 2] == pytest.approx(0)
    assert assembly.anchor.bounds[0, 2] == pytest.approx(0)
    assert all(m.is_volume for m in (assembly.model, assembly.flange, assembly.anchor))
    assert intersection_volume(assembly.model, assembly.anchor) < 1e-6
    assert intersection_volume(assembly.flange, assembly.anchor) < 1e-6
    footprint = contact_footprint(assembly.model)
    assert intersection_volume(prism(footprint, 0, h), assembly.anchor) < 1e-6
    flange_top = prism(contact_footprint(assembly.flange), h, h + 0.1)
    assert intersection_volume(flange_top, assembly.anchor) > 1


@pytest.mark.parametrize('shape', [box(100, 100, 120, 120), Point(110, 110).buffer(10, quad_segs=16),
    Polygon([(100,100),(125,100),(125,110),(110,110),(110,125),(100,125)]),
    box(100,100,120,120).difference(box(105,105,115,115)),
    box(80,100,90,110).union(box(130,100,140,110))])
def test_shapes(shape):
    assembly = generate(prism(shape, 0, 10), Settings(), LAYERS, BED)
    check(assembly)
    if isinstance(shape, Polygon) and shape.interiors:
        hole = prism(box(106,106,114,114), 0, 1.2)
        assert intersection_volume(assembly.anchor, hole) == pytest.approx(0)
        assert intersection_volume(assembly.flange, hole) == pytest.approx(0)


@pytest.mark.parametrize('mirror', [1, -1])
def test_world_transform(model, mirror):
    matrix = trimesh.transformations.rotation_matrix(0.4, [0,0,1], point=[110,110,0])
    if mirror == -1:
        reflection = np.diag([-1., 1., 1., 1.]); reflection[0,3] = 220
        matrix = matrix @ reflection
    moved = transformed(model, matrix)
    original = moved.vertices.copy()
    assembly = generate(moved, Settings(), LAYERS, BED)
    assert np.array_equal(assembly.model.vertices, original)
    check(assembly)


def test_heights_and_determinism(model):
    for height in [0.4,0.6,0.8,1,1.2,2,3]:
        a = generate(model, replace(Settings(), flange_height=height), LAYERS, BED)
        assert a.flange.bounds[1,2] == pytest.approx(height)
    a = generate(model, Settings(), LAYERS, BED)
    b = generate(model, Settings(), LAYERS, BED)
    assert np.array_equal(a.anchor.vertices, b.anchor.vertices)
    assert np.array_equal(a.anchor.faces, b.anchor.faces)


def test_layer_alignment():
    assert align_heights(Settings(), [0.3,0.45,0.65,0.85,1.05,1.3,1.5]) == pytest.approx((0.85,1.3))
    assert align_heights(replace(Settings(), flange_height=0.4), [0.3,0.5,0.7,0.9,1.1]) == pytest.approx((0.5,0.9))
    for bad in [[], [0.2,0.2], [0.3,0.2], [float('nan')], [0.2,0.4]]:
        with pytest.raises(ValueError): align_heights(Settings(), bad)


def test_rejections(model):
    near_edge = transformed(model, trimesh.transformations.translation_matrix([-100,0,0]))
    with pytest.raises(ValueError, match='bed'): generate(near_edge, Settings(), LAYERS, BED)
    with pytest.raises(ValueError, match='excluded'): generate(model, Settings(), LAYERS, BED, excluded=[box(90,90,100,100)])
    with pytest.raises(ValueError, match='another object'): generate(model, Settings(), LAYERS, BED, obstacles=[prism(box(85,100,88,110),0,5)])
    with pytest.raises(ValueError, match='Gap'): generate(model, replace(Settings(), gap=0.6), LAYERS, BED)
    with pytest.raises(ValueError): generate(model, Settings(), LAYERS, BED, slots=1)
    with pytest.raises(ValueError): generate(model, replace(Settings(), overlap=5), LAYERS, BED)
    with pytest.raises(ValueError): generate(model, replace(Settings(), gap=float('nan')), LAYERS, BED)
    with pytest.raises(ValueError): generate(model, replace(Settings(), main_slot=True), LAYERS, BED)
    broken = model.copy(); broken.update_faces(np.arange(len(broken.faces)-1))
    with pytest.raises(ValueError, match='watertight'): generate(broken, Settings(), LAYERS, BED)
    raised = transformed(model, trimesh.transformations.translation_matrix([0,0,0.2]))
    with pytest.raises(ValueError, match='Z=0'): generate(raised, Settings(), LAYERS, BED)
    degenerate = model.copy(); degenerate.faces[0] = [0,0,0]
    with pytest.raises(ValueError, match='degenerate'): generate(degenerate, Settings(), LAYERS, BED)


def test_lower_overhang_adapts_flange_and_clamp():
    stem = prism(box(100,100,120,120),0,0.6)
    head = prism(box(98,98,122,122),0.6,5)
    model = trimesh.boolean.union([stem,head], engine='manifold')
    original=model.vertices.copy()
    assembly=generate(model, Settings(), LAYERS, BED)
    check(assembly)
    assert np.array_equal(assembly.model.vertices,original)
    assert assembly.report['outline_source']=='model geometry from bed to clamp top'


def test_sloped_lower_walls_are_preserved():
    model=trimesh.creation.box([20,20,10])
    model.vertices[model.vertices[:,2]>0,:2]*=1.3
    model.apply_translation([110,110,5])
    original=model.vertices.copy()
    assembly=generate(model,replace(Settings(),flange_object_gap=0),LAYERS,BED)
    check(assembly)
    assert np.array_equal(assembly.model.vertices,original)
    # The inner flange wall follows the slope instead of cutting through it.
    assert len(assembly.flange.vertices)>16


def test_high_overhang_does_not_expand_lower_anchor():
    model=trimesh.boolean.union([prism(box(100,100,120,120),0,5),
                                prism(box(90,90,130,130),5,10)],engine='manifold')
    assembly=generate(model,Settings(),LAYERS,BED)
    check(assembly)
    assert assembly.anchor.bounds[:,:2]==pytest.approx(np.array([[85,85],[135,135]]))


@pytest.mark.parametrize('gap',[0,0.1,0.5])
@pytest.mark.parametrize('sloped',[False,True])
def test_flange_object_gap_clears_lower_wall_and_preserves_anchor(gap,sloped):
    model=trimesh.creation.box([20,20,10])
    if sloped:model.vertices[model.vertices[:,2]>0,:2]*=1.3
    model.apply_translation([110,110,5])
    settings=replace(Settings(),flange_object_gap=gap)
    assembly=generate(model,settings,LAYERS,BED)
    check(assembly)
    assert np.array_equal(assembly.model.vertices,model.vertices)
    if gap>0:
        distance=contact_footprint(assembly.flange).distance(lower_outline(model,settings.flange_height))
        assert distance==pytest.approx(gap,abs=1e-6)
    assert assembly.report['settings']['gap']==0  # Independent flange-to-anchor gap.
    assert assembly.report['settings']['flange_object_gap']==gap


@pytest.mark.parametrize('gap',[-0.1,2.1,float('nan'),True])
def test_invalid_flange_object_gap_is_rejected(gap):
    with pytest.raises(ValueError,match='flange_object_gap'):
        replace(Settings(),flange_object_gap=gap).validate(2)


def test_object_gap_must_leave_clamp_support():
    with pytest.raises(ValueError,match='clamp support'):
        replace(Settings(),flange_width=2,overlap=1,flange_object_gap=1).validate(2)


def test_disabled(model):
    a = generate(model, replace(Settings(), enabled=False), [], BED, slots=1)
    assert a.flange is None and a.anchor is None
    assert np.array_equal(model.vertices, a.model.vertices)
    assert np.array_equal(model.faces, a.model.faces)
