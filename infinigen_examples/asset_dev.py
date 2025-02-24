import argparse
import os
import sys
from pathlib import Path
import itertools
import logging
from copy import copy

logging.basicConfig(
    format='[%(asctime)s.%(msecs)03d] [%(name)s] [%(levelname)s] | %(message)s',
    datefmt='%H:%M:%S',
    level=logging.WARNING
)

import bpy
import mathutils

import gin
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from pprint import pformat
import imageio

from infinigen.assets.lighting import sky_lighting

from infinigen.core.placement.factory import AssetFactory
from infinigen.core.placement.camera import spawn_camera, set_active_camera
from infinigen.core.nodes import Nodes, NodeWrangler
from infinigen.core.util import blender as butil
from infinigen.core.util.math import FixedSeed

from infinigen.core import execute_tasks, surface, init

logging.basicConfig(level=logging.INFO)

def my_shader(nw: NodeWrangler, params: dict):

    ## TODO: Implement a more complex procedural shader

    noise_texture = nw.new_node(
        Nodes.NoiseTexture, 
        input_kwargs={
            'Scale': params['noise_scale'], 
            'Distortion': params['noise_distortion']
        }
    )
    
    principled_bsdf = nw.new_node(Nodes.PrincipledBSDF, input_kwargs={'Base Color': noise_texture.outputs["Color"]})
    
    normal = nw.new_node('ShaderNodeNormal')
    
    displacement = nw.new_node('ShaderNodeDisplacement',
        input_kwargs={'Height': noise_texture.outputs["Fac"], 'Scale': 0.02, 'Normal': normal.outputs["Normal"]})
    
    material_output = nw.new_node(Nodes.MaterialOutput,
        input_kwargs={'Surface': principled_bsdf, 'Displacement': displacement},
        attrs={'is_active_output': True})

class MyAsset(AssetFactory):

    def __init__(self, factory_seed: int, overrides=None):
        super().__init__(factory_seed)
        
        with FixedSeed(factory_seed):
            self.params = self.sample_params()
            if overrides is not None:
                self.params.update(overrides)

    def sample_params(self):
        return {

            # TODO: Add more randomized parameters

            'major_radius': np.random.uniform(1, 2),
            'minor_radius': np.random.uniform(0.1, 1),
            'noise_scale': np.random.uniform(1, 20),
            'noise_distortion': np.random.uniform(0, 5),
        }

    def create_asset(self, **_):

        ## TODO: Implement a more complex procedural mesh

        bpy.ops.mesh.primitive_torus_add(
            major_segments=100,
            minor_segments=50,
            major_radius=self.params['major_radius'],
            minor_radius=self.params['minor_radius']
        )
        obj = bpy.context.active_object
        bpy.ops.object.shade_smooth()
        
        surface.add_material(obj, my_shader, input_kwargs=dict(params=self.params))
        
        return obj

@gin.configurable
def compose_scene(output_folder, scene_seed, overrides=None, **params):

    ## TODO: Customize this function to arrange your scene, or add other assets

    sky_lighting.add_lighting()

    cam = spawn_camera()
    cam.location = (7, 7, 3.5)
    cam.rotation_euler = np.deg2rad((70, 0, 135))
    set_active_camera(cam)

    factory = MyAsset(factory_seed=np.random.randint(0, 1e7))
    if overrides is not None:
        factory.params.update(overrides)

    factory.spawn_asset(i=np.random.randint(0, 1e7))

def iter_overrides(ranges):
    mid_vals = {k: v[len(v)//2] for k, v in ranges.items()}
    for k, v in ranges.items():
        for vi in v:
            res = copy(mid_vals)
            res[k] = vi
            yield res

def create_param_demo(args, seed):

    override_ranges = {
        'major_radius': np.linspace(1, 2, num=3),
        'minor_radius': np.linspace(0.1, 1, num=3),
        'noise_scale': np.linspace(1, 20, num=3),
        'noise_distortion': np.linspace(0, 5, num=3),
    }
    for i, overrides in enumerate(iter_overrides(override_ranges)):
        
        
        butil.clear_scene()
        print(f'{i=} {overrides=}')
        with FixedSeed(seed):
            compose_scene(args.output_folder, seed, overrides=overrides)
        
        if args.save_blend:
            butil.save_blend(args.output_folder/f'scene_{i}.blend', verbose=True)

        bpy.context.scene.frame_set(i)
        bpy.context.scene.frame_start = i
        bpy.context.scene.frame_end = i
        bpy.ops.render.render(animation=True)

        imgpath = args.output_folder/f'{i:04d}.png'
        img = Image.open(imgpath)
        ImageDraw.Draw(img).text(
            xy=(10, 10), 
            text='\n'.join(f'{k}: {v:.2f}' for k, v in overrides.items()), 
            fill=(76, 252, 85),
<<<<<<< HEAD
            # font=ImageFont.truetype("arial.ttf", size=50)
            font=ImageFont.load_default()
=======
            font=ImageFont.load_default(size=50)
>>>>>>> 7bcefb377538ae9f26c02f0f04be4f45390e2be7
        )
        img.save(imgpath)
        

def create_video(args, seed):
    butil.clear_scene()
    with FixedSeed(seed):
        compose_scene(args.output_folder, seed)

    butil.save_blend(args.output_folder/'scene.blend', verbose=True)

    bpy.context.scene.frame_start = 0
    bpy.context.scene.frame_end = args.duration_frames
    bpy.ops.render.render(animation=True)



if __name__ == "__main__":

    parser = argparse.ArgumentParser()
    parser.add_argument('--output_folder', type=Path)
    parser.add_argument('--mode', type=str, choices=['param_demo', 'video'])
    parser.add_argument('--duration_frames', type=int, default=1)
    parser.add_argument('--save_blend', action='store_true')
    parser.add_argument('-s', '--seed', default=None, help="The seed used to generate the scene")
    parser.add_argument('-g', '--configs', nargs='+', default=['base'],
                        help='Set of config files for gin (separated by spaces) '
                             'e.g. --gin_config file1 file2 (exclude .gin from path)')
    parser.add_argument('-p', '--overrides', nargs='+', default=[],
                        help='Parameter settings that override config defaults '
                             'e.g. --gin_param module_1.a=2 module_2.b=3')
    parser.add_argument('-d', '--debug', action="store_const", dest="loglevel", const=logging.DEBUG, default=logging.INFO)

    args = init.parse_args_blender(parser)
    logging.getLogger("infinigen").setLevel(args.loglevel)

    seed = init.apply_scene_seed(args.seed)
    init.apply_gin_configs(
        configs=args.configs, 
        overrides=args.overrides,
        configs_folder='infinigen_examples/configs'
    )

    bpy.context.scene.render.engine = 'CYCLES'
    bpy.context.scene.cycles.samples = 50

    args.output_folder.mkdir(exist_ok=True, parents=True)
    bpy.context.scene.render.filepath = str(args.output_folder.absolute()) + '/'


    if args.mode == 'param_demo':
        create_param_demo(args, seed)
    elif args.mode == 'video':
        create_video(args, seed)
    else:
        raise ValueError(f'Unrecognized {args.mode=}')
    