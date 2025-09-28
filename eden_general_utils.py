import sys, os, time, math, re, subprocess, json
from datetime import datetime
import hashlib
import folder_paths
from statistics import mean
import torch
from typing import Any, Mapping
import comfy.samplers
import random
from PIL import Image, ImageOps, ImageSequence
from io import BytesIO
from fractions import Fraction
import numpy as np
import cv2
import glob
import random
import logging
import zipfile
import tarfile
import py7zr
from typing import Union, List, Tuple, Optional, Dict
import shutil
import tempfile
import folder_paths

# wildcard trick is taken from pythongossss's
class AnyType(str):
    def __ne__(self, __value: object) -> bool:
        return False

any_typ = AnyType("*")

def find_comfy_models_dir():
    return str(folder_paths.models_dir)

class Eden_Debug_Anything:
    """Node that prints the input to the console with detailed information based on datatype"""
    
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "input": (any_typ, {"default": None}),
            }
        }

    FUNCTION = "debug_anything"
    OUTPUT_NODE = True
    RETURN_TYPES = ("ANY",)
    RETURN_NAMES = ("input",)

    CATEGORY = "Eden 🌱/debug"

    def debug_anything(self, input):
        print("\n=== Eden Debug Anything ===")
        
        # Handle None case
        if input is None:
            print("Input is None")
            return input
            
        # Get input type
        input_type = type(input)
        print(f"Type: {input_type.__name__}")
        
        # Handle dictionaries
        if isinstance(input, dict):
            print("Dictionary content:")
            for key, value in input.items():
                value_type = type(value).__name__
                value_info = ""
                
                # Add shape for tensors
                if isinstance(value, torch.Tensor):
                    value_info = f" shape={value.shape}, dtype={value.dtype}"
                # Basic info for lists/tuples
                elif isinstance(value, (list, tuple)):
                    value_info = f" length={len(value)}"
                # Special handling for strings
                elif isinstance(value, str):
                    preview = value[:50] + "..." if len(value) > 50 else value
                    value_info = f" value=\"{preview}\""
                
                print(f"  {key}: {value_type}{value_info}")
        
        # Handle lists and tuples
        elif isinstance(input, (list, tuple)):
            print(f"{input_type.__name__} content (length={len(input)}):")
            if len(input) > 0:
                # Print type of first element
                first_type = type(input[0]).__name__
                print(f"  First element type: {first_type}")
                
                # Check if all elements are same type
                same_type = all(isinstance(x, type(input[0])) for x in input)
                print(f"  All same type: {same_type}")
                
                # Show first few elements
                max_preview = min(5, len(input))
                for i in range(max_preview):
                    item = input[i]
                    item_repr = str(item)
                    if len(item_repr) > 50:
                        item_repr = item_repr[:50] + "..."
                    print(f"  [{i}]: {item_repr}")
                
                if len(input) > max_preview:
                    print(f"  ... and {len(input) - max_preview} more elements")
        
        # Handle tensors
        elif isinstance(input, torch.Tensor):
            print(f"Tensor information:")
            print(f"  Shape: {input.shape}")
            print(f"  Dtype: {input.dtype}")
            print(f"  Device: {input.device}")
            
            # Stats for numeric tensors
            if torch.is_floating_point(input) or torch.is_complex(input) or input.dtype in [torch.int32, torch.int64]:
                try:
                    print(f"  Min: {input.min().item()}")
                    print(f"  Max: {input.max().item()}")
                    print(f"  Mean: {input.mean().item()}")
                    print(f"  Std: {input.std().item()}")
                    # Show non-zero elements
                    non_zero = torch.count_nonzero(input).item()
                    total = input.numel()
                    print(f"  Non-zero elements: {non_zero}/{total} ({non_zero/total:.2%})")
                except Exception as e:
                    print(f"  Stats calculation error: {str(e)}")
            
            # Sample values for small tensors
            if input.numel() < 20:
                print(f"  Values: {input.tolist()}")
            else:
                try:
                    flat = input.flatten()
                    sample_idx = torch.linspace(0, flat.numel()-2, 5).long()
                    samples = flat[sample_idx].tolist()
                    print(f"  Sample values: {samples}")
                except Exception as e:
                    pass
        
        # Handle strings
        elif isinstance(input, str):
            print(f"String content (length={len(input)}):")
            if len(input) > 200:
                print(f"  Preview: \"{input[:200]}...\"")
            else:
                print(f"  Full string: \"{input}\"")
                
            # Check if it looks like a file path
            if os.path.sep in input:
                print(f"  Might be a file path. Exists: {os.path.exists(input)}")
                
            # Check if it looks like JSON
            if input.strip().startswith('{') and input.strip().endswith('}'):
                print("  Might be JSON")
                
            # Check if it contains newlines
            newline_count = input.count('\n')  # Use raw string to avoid the issue
            print(f"  Contains {newline_count} newlines")
        
        # Handle numbers
        elif isinstance(input, (int, float)):
            print(f"Numeric value: {input}")
            if isinstance(input, float):
                print(f"  As fraction: {input.as_integer_ratio()}")
        
        # Handle objects with special attributes
        else:
            # Try common attributes
            common_attrs = ['shape', 'size', 'dtype', 'name', 'mode', 'filename', 'metadata']
            for attr in common_attrs:
                if hasattr(input, attr):
                    try:
                        value = getattr(input, attr)
                        print(f"  {attr}: {value}")
                    except:
                        pass
            
            # Try dir() for all public attributes
            attrs = [a for a in dir(input) if not a.startswith('_') and not callable(getattr(input, a, None))]
            if attrs and len(attrs) < 15:  # Only show if not too many
                print("  Public attributes:")
                for attr in attrs[:10]:  # Limit to first 10
                    try:
                        value = getattr(input, attr)
                        value_str = str(value)
                        if len(value_str) > 50:
                            value_str = value_str[:50] + "..."
                        print(f"    {attr}: {value_str}")
                    except:
                        print(f"    {attr}: <error getting value>")
                        
                if len(attrs) > 10:
                    print(f"    ... and {len(attrs) - 10} more attributes")
        
        print("===========================\n")
        return (input, )

class Eden_Regex_Replace:
    """Node that performs regex-based string replacement operations"""
    
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "source_string": ("STRING", {"multiline": True, "default": ""}),
                "regex_pattern": ("STRING", {"default": ""}),
                "replacement": ("STRING", {"default": ""}),
                "max_n_replacements": ("INT", {"default": -1, "min": -1, "max": 1000000, "step": 1}),
                "case_sensitive": ("BOOLEAN", {"default": True}),
            }
        }

    FUNCTION = "regex_replace"
    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("result_string",)

    CATEGORY = "Eden 🌱/text"

    def regex_replace(self, source_string, regex_pattern, replacement="", max_n_replacements=-1, case_sensitive=True):
        """
        Performs regex-based string replacement
        
        Args:
            source_string: The input text to process
            regex_pattern: The regex pattern to search for
            replacement: The replacement text (can include backreferences like \1, \2, etc.)
            max_n_replacements: Maximum number of replacements to make (-1 = all)
            case_sensitive: Whether the pattern matching should be case-sensitive
            
        Returns:
            The resulting string after replacement
        """
        # Handle empty or None inputs
        if not source_string or not regex_pattern:
            return source_string
            
        try:
            # Set regex flags
            flags = 0 if case_sensitive else re.IGNORECASE
            
            # Convert -1 to 0 for re.sub since it uses 0 to replace all instances
            count = 0 if max_n_replacements == -1 else max_n_replacements
            
            # Perform the replacement
            result = re.sub(
                pattern=regex_pattern,
                repl=replacement,
                string=source_string,
                count=count,
                flags=flags
            )
            
            return (result, )
            
        except Exception as e:
            # Return original string with error indication if the regex is invalid
            return f"REGEX ERROR: {str(e)}\nOriginal: {source_string}"

class Eden_FloatToInt:
    @classmethod
    def INPUT_TYPES(cls) -> Mapping[str, Any]:
        return {"required": {"a": ("FLOAT", {"default": 0.0, "round": False})}}

    RETURN_TYPES = ("INT",)
    FUNCTION = "op"
    CATEGORY = "Eden 🌱/general"

    def op(self, a: float) -> tuple[int]:
        return (int(a),)

class Eden_IntToFloat:
    @classmethod
    def INPUT_TYPES(cls) -> Mapping[str, Any]:
        return {"required": {"a": ("INT", {"default": 0, "max": sys.maxsize})}}

    RETURN_TYPES = ("FLOAT",)
    FUNCTION = "op"
    CATEGORY = "Eden 🌱/general"

    def op(self, a: int) -> tuple[float]:
        return (float(a),)

class Eden_StringHash:
    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                "input_string": ("STRING", {"default": "", "multiline": True}),
                "hash_length": ("INT", {
                    "default": 8,
                    "min": 4,
                    "max": 64,
                    "step": 1,
                }),
            }
        }

    RETURN_TYPES = ("INT", "STRING")
    RETURN_NAMES = ("hash_int", "hash_string")
    FUNCTION = "generate_hash"
    CATEGORY = "Eden 🌱/general"
    DESCRIPTION = "Generates a deterministic hash from an input string with configurable length"

    def generate_hash(self, input_string: str, hash_length: int = 8):
        hasher = hashlib.md5(input_string.encode('utf-8'))
        
        # Get the first N bytes of the hash and convert to integer
        hash_bytes = hasher.digest()[:min(8, hash_length)]
        hash_int = int.from_bytes(hash_bytes, byteorder='big')
        
        # Return a truncated hex string based on desired length
        hash_string = hasher.hexdigest()[:hash_length]
        
        return (hash_int, hash_string,)
    
class Eden_Seed:
    @classmethod
    def INPUT_TYPES(s):
        return {'required': {'seed': ('INT', {'default': 0, 'min': 0, 'max': 0xffffffffffffffff})}}

    RETURN_TYPES = ('INT','STRING')
    RETURN_NAMES = ('seed','seed_string')
    FUNCTION = 'output'
    CATEGORY = "Eden 🌱/general"

    def output(self, seed):
        seed_string = str(seed)
        return (seed, seed_string,)

class Eden_Math:
    """Node to evaluate a simple math expression string with variables a, b, c"""
    
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "expression": ("STRING", {"default": "", "multiline": False}),
            },
            "optional": {
                "a": (any_typ, {"default": 0.0}),
                "b": (any_typ, {"default": 0.0}),
                "c": (any_typ, {"default": 0.0}),
            }
        }

    FUNCTION = "eval_expression"
    RETURN_TYPES = ("FLOAT", "INT", "STRING")
    RETURN_NAMES = ("result (float)", "result (int)", "result (float_str)")
    CATEGORY = "Eden 🌱/general"
    DESCRIPTION = (
        "evaluate a simple math expression string with variables a, b, c, supports basic math and functions"
    )

    def eval_expression(self, expression: str, a = 0.0, b = 0.0, c = 0.0):
        allowed_functions = {
            'min': min,
            'max': max,
            'mean': mean,
            'sqrt': math.sqrt,
            '^': pow,
            'pow': pow,
        }

        a = float(a)
        b = float(b)
        c = float(c)

        # Add variables a, b, c to the namespace
        local_vars = {'a': a, 'b': b, 'c': c, **allowed_functions}

        # Replace caret symbol (^) with '**' for power operation
        expression = expression.replace('^', '**')

        result = -1
        try:
            result = eval(expression, {"__builtins__": None}, local_vars)
        except SyntaxError as e:
            raise ValueError(
                f"The expression syntax is wrong '{expression}': {e}"
            ) from e
        except Exception as e:
            raise ValueError(
                f"Error evaluating math expression '{expression}': {e}"
            )
        
        return (float(result), int(round(result)), str(round(result, 3)))

class Eden_Image_Math:
    """Node to evaluate a simple math expression on image or mask tensors"""
    
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "expression": ("STRING", {"default": "", "multiline": False}),
                "conversion_mode": (["mean", "r", "g", "b"], {"default": "mean"}),
            },
            "optional": {
                "a": (any_typ, {"default": None}),
                "b": (any_typ, {"default": None}),
                "c": (any_typ, {"default": None}),
            }
        }

    FUNCTION = "eval_expression"
    RETURN_TYPES = ("IMAGE", "MASK")
    CATEGORY = "Eden 🌱/image"
    DESCRIPTION = (
        "Apply math expression to image/mask tensors a,b and c, supports basic math and functions. "
        "Example: 'sin(a*pi) * b + c' applies trigonometric operation to a, multiplies by b and adds c. "
        "Masks are automatically broadcasted to match image dimensions. "
        "Returns both IMAGE and MASK formats with configurable RGB->mask conversion behavior."
    )

    def convert_mask_to_image(self, mask_tensor):
        """Convert a mask tensor (B,H,W,1) to image tensor (B,H,W,3)"""
        return mask_tensor.repeat(1, 1, 1, 3)

    def convert_image_to_mask(self, image_tensor, mode="mean"):
        """Convert an image tensor (B,H,W,3) to mask tensor (B,H,W,1)"""
        if mode == "mean":
            return torch.mean(image_tensor, dim=-1, keepdim=True)
        elif mode in ["r", "g", "b"]:
            channel = {"r": 0, "g": 1, "b": 2}[mode]
            return image_tensor[:, :, :, channel:channel+1]
        else:
            raise ValueError(f"Unsupported conversion mode: {mode}")

    def eval_expression(self, expression: str, conversion_mode: str, a=None, b=None, c=None):
        # Updated pattern to properly match allowed characters without problematic escapes
        allowed_pattern = r'^[a-zA-Z0-9\s+\-*/(),.\^]+$'
        if not re.match(allowed_pattern, expression):
            raise ValueError(f"Expression contains invalid characters: {expression}")

        # Check which variables are used in the expression
        used_vars = {var: var in expression for var in ['a', 'b', 'c']}

        # Validate inputs against expression needs
        if used_vars['a'] and a is None:
            raise ValueError("Expression uses 'a' but no input was provided for a")
        if used_vars['b'] and b is None:
            raise ValueError("Expression uses 'b' but no input was provided for b")
        if used_vars['c'] and c is None:
            raise ValueError("Expression uses 'c' but no input was provided for c")

        # Create namespace for evaluation
        namespace = {}

        # Helper function to handle broadcasting of masks to match image dimensions
        def broadcast_input(tensor, target_shape):
            if tensor is None:
                return None
                
            # Check if input is a mask (B,H,W,1) vs image (B,H,W,3)
            is_mask = tensor.shape[-1] == 1
            target_channels = target_shape[-1]
            
            # Handle broadcasting between masks and images
            if is_mask and target_channels == 3:
                tensor = self.convert_mask_to_image(tensor)
            elif not is_mask and target_channels == 1:
                tensor = self.convert_image_to_mask(tensor, conversion_mode)
            
            # Handle batch dimension
            if tensor.shape[0] == 1 and target_shape[0] > 1:
                tensor = tensor.repeat(target_shape[0], 1, 1, 1)
            
            # Use torch's broadcast_to for final shape matching
            try:
                new_shape = list(target_shape)
                new_shape[-1] = tensor.shape[-1]  # Preserve channel dimension
                tensor = torch.broadcast_to(tensor, new_shape)
            except RuntimeError as e:
                raise ValueError(f"Cannot broadcast tensor of shape {tensor.shape} to shape {new_shape}: {str(e)}")
                
            return tensor

        # Determine target shape from first input
        target_shape = a.shape if a is not None else (b.shape if b is not None else c.shape)
        
        # Process inputs
        if a is not None:
            namespace['a'] = broadcast_input(a, target_shape)
        if b is not None:
            namespace['b'] = broadcast_input(b, target_shape)
        if c is not None:
            namespace['c'] = broadcast_input(c, target_shape)

        # Add mathematical constants
        namespace['pi'] = math.pi
        namespace['e'] = math.e

        # Add comprehensive set of torch operations
        torch_functions = {
            # Basic math
            'sqrt': torch.sqrt,
            'pow': torch.pow,
            '^': torch.pow,
            'abs': torch.abs,
            'round': torch.round,
            'ceil': torch.ceil,
            'floor': torch.floor,
            'trunc': torch.trunc,
            'sign': torch.sign,

            # Trigonometric functions
            'sin': torch.sin,
            'cos': torch.cos,
            'tan': torch.tan,
            'asin': torch.asin,
            'acos': torch.acos,
            'atan': torch.atan,
            'sinh': torch.sinh,
            'cosh': torch.cosh,
            'tanh': torch.tanh,
            'asinh': torch.asinh,
            'acosh': torch.acosh,
            'atanh': torch.atanh,
            
            # Exponential and logarithmic
            'exp': torch.exp,
            'log': torch.log,
            'log2': torch.log2,
            'log10': torch.log10,
            
            # Statistics
            'mean': torch.mean,
            'min': torch.min,
            'max': torch.max,
            'median': torch.median,
            'std': torch.std,
            'var': torch.var
        }
        namespace.update(torch_functions)

        # Replace caret symbol with power operator
        expression = expression.replace('^', '**')

        try:
            result = eval(expression, {"__builtins__": None}, namespace)
        except Exception as e:
            raise ValueError(f"Error evaluating expression '{expression}': {str(e)}")

        # Always ensure result is in float format
        result = result.float()

        # Always return both IMAGE and MASK formats
        if result.shape[-1] == 3:
            return (result, self.convert_image_to_mask(result, conversion_mode))
        else:
            return (self.convert_mask_to_image(result), result)

class IP_Adapter_Settings_Distribution:
    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                "weight": ("FLOAT", {"default": 1.0, "min": -1.0, "max": 2.0, "step": 0.01}),
                "weight_type": (["linear", "ease in", "ease out", 'ease in-out', 'reverse in-out', 'weak input', 'weak output', 'weak middle', 'strong middle', 'style transfer', 'composition', 'strong style transfer', 'style and composition', 'style transfer precise', 'composition precise'],),
            },
        }
    RETURN_TYPES = ("FLOAT", any_typ)
    RETURN_NAMES = ("weight", "weight_type")
    FUNCTION = "set"
    CATEGORY = "Eden 🌱/general"

    def set(self, weight, weight_type):
        return (weight, weight_type)
    
class Eden_StringReplace:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "input_string": ("STRING", {"default": "", "multiline": True}),
                "target_text": ("STRING", {"default": "", "multiline": False}),
                "replace_with": ("STRING", {"default": "", "multiline": True}),
            }
        }

    RETURN_TYPES = ("STRING",)
    FUNCTION = "replace_text"
    CATEGORY = "Eden 🌱/general"
    DESCRIPTION = "Replaces all occurrences of target text with replacement text in the input string"

    def replace_text(self, input_string: str, target_text: str, replace_with: str):
        result = input_string.replace(target_text, replace_with)
        return (result,)
    
class Eden_randbool:
    @classmethod
    def INPUT_TYPES(s):
        return {"required": {
                    "seed": ("INT", {"default": 0, "max": sys.maxsize}),
                    "probability": ("FLOAT", {"default": 0.5}),
                }
            }
    RETURN_TYPES = ("BOOLEAN",)
    RETURN_NAMES = ("bool",)
    FUNCTION = "sample"
    CATEGORY = "Eden 🌱/random_c"

    def sample(self, seed, probability):
        torch.manual_seed(seed)
        return (torch.rand(1).item() < probability,)
    
class Eden_RandomPromptFromFile:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "file_path": ("STRING", {"default": "prompts.txt"}),
                "seed": ("INT", {"default": 0, "min": 0, "max": 0xffffffffffffffff}),
            }
        }

    RETURN_TYPES = ("STRING",)
    FUNCTION = "get_random_prompt"
    CATEGORY = "Eden 🌱/general"
    DESCRIPTION = "Reads prompts from a text file (one per line) and returns a random prompt"

    def get_random_prompt(self, file_path: str, seed: int):
        
        try:
            # Read all lines from the file
            with open(file_path, 'r', encoding='utf-8') as f:
                lines = [line.strip() for line in f.readlines()]
            
            # Filter out empty lines
            lines = [line for line in lines if line]
            
            if not lines:
                raise ValueError(f"No valid prompts found in file: {file_path}")
            
            # Select a prompt
            index = seed % len(lines)
            selected_prompt = lines[index]
            
            return (selected_prompt,)
            
        except FileNotFoundError:
            raise FileNotFoundError(f"Prompt file not found: {file_path}")
        except Exception as e:
            raise Exception(f"Error reading prompt file: {str(e)}")

class Eden_RandomFilepathSampler:
    """Node that samples a random filepath from a directory with filtering options"""
    
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "directory_path": ("STRING", {"default": "./"}),
                "seed": ("INT", {"default": 0, "min": 0, "max": 0xffffffffffffffff}),
            },
            "optional": {
                "file_extension": ("STRING", {"default": ""}),
                "include_subdirectories": ("BOOLEAN", {"default": False}),
                "filter_string": ("STRING", {"default": ""}),
                "filter_mode": (["contains", "starts_with", "ends_with", "regex"], {"default": "contains"}),
                "case_sensitive": ("BOOLEAN", {"default": False}),
            }
        }

    FUNCTION = "sample_filepath"
    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("filepath",)
    CATEGORY = "Eden 🌱/random"

    def sample_filepath(self, directory_path: str, seed: int, 
                        file_extension: str = "", include_subdirectories: bool = False,
                        filter_string: str = "", filter_mode: str = "contains",
                        case_sensitive: bool = False) -> Tuple[str]:
        """
        Sample a random filepath from the given directory matching the specified criteria.
        
        Args:
            directory_path: The directory path to sample files from
            seed: Random seed for reproducible sampling
            file_extension: File extension to filter by (e.g., ".jpg", ".png")
            include_subdirectories: Whether to include files from subdirectories
            filter_string: String to filter filenames by
            filter_mode: How to apply the filter_string (contains, starts_with, ends_with, regex)
            case_sensitive: Whether string filtering should be case-sensitive
            
        Returns:
            A tuple containing the randomly selected filepath as a string
        """
        # Set random seed for reproducibility
        random.seed(seed)
        
        # Clean up input parameters
        directory_path = os.path.expanduser(directory_path)  # Expand ~ if present
        if file_extension and not file_extension.startswith('.'):
            file_extension = '.' + file_extension
        
        # Validate directory exists
        if not os.path.isdir(directory_path):
            raise ValueError(f"Directory not found: {directory_path}")
        
        # Gather all files based on the include_subdirectories flag
        all_files = []
        
        if include_subdirectories:
            for root, _, files in os.walk(directory_path):
                for file in files:
                    all_files.append(os.path.join(root, file))
        else:
            all_files = [os.path.join(directory_path, f) for f in os.listdir(directory_path) 
                        if os.path.isfile(os.path.join(directory_path, f))]
        
        # Filter by extension if specified
        if file_extension:
            all_files = [f for f in all_files if f.lower().endswith(file_extension.lower())]
        
        # Apply additional filename filtering if specified
        if filter_string:
            filtered_files = []
            
            for filepath in all_files:
                filename = os.path.basename(filepath)
                
                # Apply case sensitivity
                compare_filename = filename if case_sensitive else filename.lower()
                compare_filter = filter_string if case_sensitive else filter_string.lower()
                
                # Apply filtering based on selected mode
                if filter_mode == "contains":
                    if compare_filter in compare_filename:
                        filtered_files.append(filepath)
                elif filter_mode == "starts_with":
                    if compare_filename.startswith(compare_filter):
                        filtered_files.append(filepath)
                elif filter_mode == "ends_with":
                    if compare_filename.endswith(compare_filter):
                        filtered_files.append(filepath)
                elif filter_mode == "regex":
                    import re
                    flags = 0 if case_sensitive else re.IGNORECASE
                    if re.search(filter_string, filename, flags):
                        filtered_files.append(filepath)
            
            all_files = filtered_files

        # Remove weird / os specific hidden files:
        all_files = [f for f in all_files if not os.path.basename(f).startswith('.')]
        
        # Check if any files match the criteria
        if not all_files:
            raise ValueError(f"No files found matching the specified criteria in {directory_path}")
        
        selected_file = random.choice(all_files)
        
        return (selected_file,)

class Eden_RepeatLatentBatch:
    @classmethod
    def INPUT_TYPES(s):
        return {"required": { "samples": ("LATENT",),
                              "amount": ("INT", {"default": 1, "min": 1, "max": 1024}),
                              }}
    RETURN_TYPES = ("LATENT",)
    FUNCTION = "repeat"
    CATEGORY = "Eden 🌱/general"

    def repeat(self, samples, amount):
        s = samples.copy()
        s_in = samples["samples"]
        
        s["samples"] = s_in.repeat((amount, 1,1,1))
        if "noise_mask" in samples and samples["noise_mask"].shape[0] > 1:
            masks = samples["noise_mask"]
            if masks.shape[0] < s_in.shape[0]:
                masks = masks.repeat(math.ceil(s_in.shape[0] / masks.shape[0]), 1, 1, 1)[:s_in.shape[0]]
            s["noise_mask"] = samples["noise_mask"].repeat((amount, 1,1,1))
        if "batch_index" in s:
            offset = max(s["batch_index"]) - min(s["batch_index"]) + 1
            s["batch_index"] = s["batch_index"] + [x + (i * offset) for i in range(1, amount) for x in s["batch_index"]]
        return (s,)

class Eden_DetermineFrameCount:
    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                "n_target_frames": ("INT", {"default": 24, "min": 0, "max": 1024}),
                "n_source_frames": ("INT", {"default": 1, "min": 0, "max": 1024}),
                "policy": (["closest", "round down", "round up"],),
                "min_frames": ("INT", {"default": 1, "min": 0, "max": 1024, "step": 1}),
                "max_frames": ("INT", {"default": 1024, "min": 0, "max": 1024, "step": 1}),
            },
        }
    
    RETURN_TYPES = ("INT",)
    FUNCTION = "determine_frame_count"
    CATEGORY = "Eden 🌱/general"

    def determine_frame_count(self, n_target_frames, n_source_frames, policy, min_frames, max_frames):
        # Validate min/max values
        if min_frames > max_frames:
            min_frames, max_frames = max_frames, min_frames

        # Early returns for special cases
        if n_target_frames == 0:
            return (max(min_frames, min(0, max_frames)),)
        
        if n_source_frames <= 1:
            return (max(min_frames, min(n_target_frames, max_frames)),)
        
        # Calculate output based on policy
        result = n_target_frames  # default fallback
        
        if policy == "closest":
            result = round(n_target_frames / n_source_frames) * n_source_frames
        elif policy == "round down":
            result = (n_target_frames // n_source_frames) * n_source_frames
            result = max(n_source_frames, result)  # Ensure we don't go below n_source_frames
        elif policy == "round up":
            result = math.ceil(n_target_frames / n_source_frames) * n_source_frames
        
        # Clamp the result between min and max frames
        result = max(min_frames, min(result, max_frames))
        
        return (int(result),)

class SDTypeConverter:
    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {},
            "optional": {
                "model_name": (
                    folder_paths.get_filename_list("checkpoints"),
                    {"forceInput": True},
                ),
                "sampler_name": (
                    comfy.samplers.KSampler.SAMPLERS,
                    {"forceInput": True},
                ),
                "scheduler": (
                    comfy.samplers.KSampler.SCHEDULERS,
                    {"forceInput": True}
                ),
            },
        }

    RETURN_TYPES = (
        "STRING",
        "STRING",
        "STRING",
    )

    RETURN_NAMES = (
        "MODEL_NAME_STR",
        "SAMPLER_NAME_STR",
        "SCHEDULER_STR",
    )

    FUNCTION = "convert_string"
    CATEGORY = "SD Prompt Reader"

    def convert_string(
        self, model_name: str = "", sampler_name: str = "", scheduler: str = ""
    ):
        return (
            model_name,
            sampler_name,
            scheduler,
        )

class SDAnyConverter:
    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {},
            "optional": {
                "any_type_input": (
                    any_typ,
                    {"forceInput": True},
                ),
            },
        }

    RETURN_TYPES = (any_typ,)
    RETURN_NAMES = ("ANY_TYPE_OUTPUT",)
    FUNCTION = "convert_any"
    CATEGORY = "SD Prompt Reader"

    def convert_any(self, any_type_input: str = ""):
        return (any_type_input,)

# Initialize logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

ffmpeg_path = shutil.which("ffmpeg")
if not ffmpeg_path:
    ffmpeg_path = "ffmpeg"  # Fall back to just the command name, assuming it's in PATH

def pil_to_tensor(image: Image.Image) -> torch.Tensor:
    """Convert PIL image to PyTorch tensor in ComfyUI format (B,H,W,C)."""
    if image.mode != 'RGB':
        image = image.convert('RGB')
    
    # Convert to numpy array and normalize to 0-1 range
    np_image = np.array(image).astype(np.float32) / 255.0
    
    # Convert to tensor with batch dimension (B,H,W,C)
    # PIL/numpy arrays are already in (H,W,C) format, just add batch dimension
    tensor = torch.from_numpy(np_image).unsqueeze(0)
    
    return tensor

def resize_image_max_size(image: Image.Image, max_res: int) -> Image.Image:
    """Resize image if its width or height exceeds max_res, preserving aspect ratio."""
    if max_res <= 0:
        return image
    
    w, h = image.size
    if w <= max_res and h <= max_res:
        return image
    
    # Calculate new dimensions preserving aspect ratio
    if w > h:
        new_w = max_res
        new_h = int(h * (max_res / w))
    else:
        new_h = max_res
        new_w = int(w * (max_res / h))
    
    # Resize using Lanczos resampling for quality
    return image.resize((new_w, new_h), Image.Resampling.LANCZOS)

def load_path(path: str) -> Union[str, List[str]]:
    """
    Resolves a path that can be either:
    - An absolute path to a file or directory
    - A relative path from input directory to a file or directory
    - A path with [input]/[output]/[temp] annotations
    - A wildcard pattern for image files
    
    Returns either a single path string or list of paths if wildcards matched multiple images
    """
    path = path.strip('"').strip("'").replace("\\", "/")
    
    # Handle annotated paths
    if "[" in path:
        name, base_dir = folder_paths.annotated_filepath(path)
        if base_dir is not None:
            full_path = os.path.join(base_dir, name)
            # Check for wildcards in image patterns
            if ('*' in name or '?' in name) and any(name.lower().endswith(ext) for ext in ['.png', '.jpg', '.jpeg', '.webp', '.gif']):
                matches = glob.glob(full_path, recursive=True)
                if matches:
                    return [os.path.abspath(p) for p in matches]
            elif os.path.exists(full_path):
                return os.path.abspath(full_path)
    
    # Try as absolute path with wildcards for images
    if ('*' in path or '?' in path) and any(path.lower().endswith(ext) for ext in ['.png', '.jpg', '.jpeg', '.webp', '.gif']):
        matches = glob.glob(path, recursive=True)
        if matches:
            return [os.path.abspath(p) for p in matches]
    elif os.path.exists(path):
        return os.path.abspath(path)
        
    # Try in input directory
    input_path = os.path.join(folder_paths.get_input_directory(), path)
    if ('*' in path or '?' in path) and any(path.lower().endswith(ext) for ext in ['.png', '.jpg', '.jpeg', '.webp', '.gif']):
        matches = glob.glob(input_path, recursive=True)
        if matches:
            return [os.path.abspath(p) for p in matches]
    elif os.path.exists(input_path):
        return os.path.abspath(input_path)
            
    raise FileNotFoundError(f"Could not find file or directory at {path} or {input_path}")

def _extract_frames_from_video_generator(video_path: str, force_rate: float = 0.0,
                                         image_load_cap: int = 0, max_res: int = 0):
    """
    Extracts frames from a video file using OpenCV, yielding them as NumPy arrays.
    Yields:
        Tuple: (fps, num_frames_to_yield, first_frame_width, first_frame_height)
        np.ndarray: Processed frame (H, W, C) as float32, normalized 0-1.
    """
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        raise ValueError(f"Cannot open video file: {video_path}")

    original_fps = cap.get(cv2.CAP_PROP_FPS)
    total_frames_in_video = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

    frame_interval = 1
    if force_rate > 0 and original_fps > 0:
        frame_interval = max(1, round(original_fps / force_rate))

    # Calculate how many frames we'll actually try to extract
    potential_frames_to_extract = (total_frames_in_video + frame_interval - 1) // frame_interval
    if image_load_cap > 0:
        num_frames_to_yield = min(image_load_cap, potential_frames_to_extract)
    else:
        num_frames_to_yield = potential_frames_to_extract

    if num_frames_to_yield == 0 and total_frames_in_video > 0: # if cap is 0 but video has frames, yield all based on interval
        num_frames_to_yield = potential_frames_to_extract
    elif num_frames_to_yield == 0 and total_frames_in_video == 0:
        cap.release()
        raise ValueError(f"No frames to extract from video: {video_path}")


    # Yield metadata: fps to report, num_frames_actually_yielded, first_frame_w, first_frame_h
    # For first_frame_w, first_frame_h, we need to read one frame
    first_frame_pil = None
    first_frame_w, first_frame_h = 0, 0

    if num_frames_to_yield > 0:
        cap.set(cv2.CAP_PROP_POS_FRAMES, 0) # Start from the beginning for the first frame
        ret, frame_cv = cap.read()
        if ret:
            frame_cv = cv2.cvtColor(frame_cv, cv2.COLOR_BGR2RGB)
            first_frame_pil = Image.fromarray(frame_cv)
            if max_res > 0:
                first_frame_pil = resize_image_max_size(first_frame_pil, max_res)
            first_frame_w, first_frame_h = first_frame_pil.size
        else: # Video might be empty or unreadable
            cap.release()
            raise ValueError(f"Could not read the first frame from video: {video_path}")
    
    reported_fps = force_rate if force_rate > 0 else original_fps
    yield (reported_fps, num_frames_to_yield, first_frame_w, first_frame_h)

    # Now yield the first frame if it was processed
    if first_frame_pil:
        if first_frame_pil.mode != 'RGB':
            first_frame_pil = first_frame_pil.convert('RGB')
        np_frame = np.array(first_frame_pil).astype(np.float32) / 255.0
        yield np_frame
        frames_yielded_count = 1
        current_frame_index_in_video = frame_interval # Next frame to read
    else: # Should not happen if num_frames_to_yield > 0 and first frame read failed
        frames_yielded_count = 0
        current_frame_index_in_video = 0


    while frames_yielded_count < num_frames_to_yield:
        if current_frame_index_in_video >= total_frames_in_video:
            break 
            
        cap.set(cv2.CAP_PROP_POS_FRAMES, current_frame_index_in_video)
        ret, frame_cv = cap.read()

        if not ret:
            break

        frame_cv = cv2.cvtColor(frame_cv, cv2.COLOR_BGR2RGB)
        pil_image = Image.fromarray(frame_cv)

        if max_res > 0:
            pil_image = resize_image_max_size(pil_image, max_res)
        
        if pil_image.mode != 'RGB':
            pil_image = pil_image.convert('RGB')
        np_frame = np.array(pil_image).astype(np.float32) / 255.0
        yield np_frame

        frames_yielded_count += 1
        current_frame_index_in_video += frame_interval
    
    cap.release()

def _process_gif_generator(gif_path: str, force_rate: float = 0.0,
                           image_load_cap: int = 0, max_res: int = 0):
    """
    Processes an animated GIF, yielding frames as NumPy arrays.
    Yields:
        Tuple: (fps, num_frames_to_yield, first_frame_width, first_frame_height)
        np.ndarray: Processed frame (H, W, C) as float32, normalized 0-1.
    """
    gif = Image.open(gif_path)

    if not getattr(gif, "is_animated", False):
        # Not animated, treat as single image
        if max_res > 0:
            gif = resize_image_max_size(gif, max_res)
        
        img_rgb = gif.convert("RGB")
        w, h = img_rgb.size
        np_frame = np.array(img_rgb).astype(np.float32) / 255.0
        yield (0.0, 1, w, h) # fps, count, w, h
        yield np_frame
        return

    try:
        original_gif_fps = 1000 / (gif.info.get('duration', 100))
    except (ZeroDivisionError, TypeError):
        original_gif_fps = 10.0

    frame_interval = 1
    if force_rate > 0 and original_gif_fps > 0:
        frame_interval = max(1, round(original_gif_fps / force_rate))

    # Calculate how many frames we'll actually try to extract
    # ImageSequence.Iterator doesn't give total frames easily, so we iterate once to count if needed for image_load_cap.
    # Or, better, we just cap as we go.
    
    # Determine num_frames_to_yield and first frame dimensions
    first_frame_pil = None
    first_frame_w, first_frame_h = 0, 0
    
    # Peek at the first frame for dimensions and to help determine num_frames_to_yield
    # We need to iterate to know the true number of frames available after interval.
    
    preview_frames_count = 0
    temp_iterator = ImageSequence.Iterator(gif)
    for i, frame_pil_peek in enumerate(temp_iterator):
        if i % frame_interval == 0:
            if preview_frames_count == 0: # This is the first frame we'd process
                frame_pil_peek_proc = frame_pil_peek.convert("RGB")
                if max_res > 0:
                    frame_pil_peek_proc = resize_image_max_size(frame_pil_peek_proc, max_res)
                first_frame_w, first_frame_h = frame_pil_peek_proc.size
            preview_frames_count +=1

    num_frames_to_yield = preview_frames_count
    if image_load_cap > 0:
        num_frames_to_yield = min(image_load_cap, preview_frames_count)

    if num_frames_to_yield == 0:
        raise ValueError(f"No frames to extract from GIF: {gif_path}")

    reported_fps = force_rate if force_rate > 0 else original_gif_fps
    yield (reported_fps, num_frames_to_yield, first_frame_w, first_frame_h)

    frames_yielded_count = 0
    for i, frame_pil in enumerate(ImageSequence.Iterator(gif)):
        if frames_yielded_count >= num_frames_to_yield:
            break
            
        if i % frame_interval != 0:
            continue
            
        frame_pil = frame_pil.convert("RGB")
        if max_res > 0:
            frame_pil = resize_image_max_size(frame_pil, max_res)
        
        np_frame = np.array(frame_pil).astype(np.float32) / 255.0
        yield np_frame
        frames_yielded_count += 1

extract_frames_from_video = _extract_frames_from_video_generator
process_gif = _process_gif_generator

def load_single_image(image_path: str, max_res: int = 0) -> torch.Tensor:
    """
    Load a single image and convert to tensor.
    
    Args:
        image_path: Path to the image file
        max_res: Maximum resolution for width or height (0 means no resize)
    
    Returns:
        Image as tensor (B,C,H,W)
    """
    # Open and process image
    img = Image.open(image_path)
    img = ImageOps.exif_transpose(img)
    
    # Resize if needed
    if max_res > 0:
        img = resize_image_max_size(img, max_res)
    
    # Convert to tensor
    tensor = pil_to_tensor(img)
    
    return tensor

def concat_image_tensors(tensors: List[torch.Tensor]) -> torch.Tensor:
    """Concatenate multiple image tensors along the batch dimension."""
    if not tensors:
        raise ValueError("No tensors to concatenate")
    
    if len(tensors) == 1:
        return tensors[0]
    
    return torch.cat(tensors, dim=0)

class Eden_AllMediaLoader:
    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                "path": ("STRING", {
                    "image_upload": True,
                    "tooltip": "Path to media file(s). Can be an image, directory of images, video file, or archive."
                }),
                "image_load_cap": ("INT", {
                    "default": 0,
                    "min": 0,
                    "max": sys.maxsize,
                    "step": 1,
                    "tooltip": "Maximum number of images to load. 0 means load all images."
                }),
                "force_rate": ("FLOAT", {
                    "default": 0.0,
                    "min": 0.0,
                    "step": 0.1,
                    "tooltip": "Force extracting frames at this FPS rate. 0 means use original rate."
                }),
                "max_res": ("INT", {
                    "default": 2048,
                    "min": 0,
                    "max": sys.maxsize,
                    "step": 1,
                    "tooltip": "Maximum resolution (width or height). Images larger than this will be resized. 0 means no resize."
                }),
                "sort": (["None", "alphabetical", "date_created", "date_modified", "random"], {
                    "default": "None",
                    "tooltip": "Method to sort multiple images."
                })
            }
        }

    RETURN_TYPES = ("IMAGE", "INT", "INT", "INT", "STRING", "STRING", "FLOAT")
    RETURN_NAMES = ("image", "WIDTH", "HEIGHT", "COUNT", "FILE_NAME", "FILE_PATH", "FPS")
    FUNCTION = "load_media"
    CATEGORY = "Eden 🌱/general"
    DESCRIPTION = """Simplified Media Loader for various sources.
    
    Features:
    - Loads images, directories, videos, and GIFs
    - Extracts frames at a specific FPS rate with force_rate
    - Automatically resizes images that exceed max_res
    - Supports basic sorting options
    - Returns tensors in ComfyUI format [B, H, W, C]
    """
    
    def load_media(self, path: str, image_load_cap: int = 0, force_rate: float = 0.0, 
                   max_res: int = 0, sort: str = "None") -> Tuple:
        """
        Main function to load media from various sources.
        
        Args:
            path: Path to the media file or directory
            image_load_cap: Maximum number of images to load (0 means all)
            force_rate: Target FPS for videos/GIFs (0 means use original rate)
            max_res: Maximum resolution (0 means no resize)
            sort: Sorting method for directories
            
        Returns:
            Tuple of (image tensor, width, height, count, filename, filepath, fps)
        """
        try:
            resolved_path = load_path(path)
            
            # If we got a list of paths from wildcard matching
            if isinstance(resolved_path, list):
                return self.process_image_list(resolved_path, image_load_cap, max_res, sort)
            
            # Handle single path (file or directory)
            path = resolved_path
            parent_directory = os.path.dirname(path) if not os.path.isdir(path) else path
            
            # Handle directories
            if os.path.isdir(path):
                return self.load_from_directory(path, image_load_cap, max_res, sort)
            
            # Handle videos
            elif path.lower().endswith(('.mp4', '.mov')):
                frame_generator = extract_frames_from_video(
                    path, force_rate, image_load_cap, max_res
                )
                metadata = next(frame_generator)
                fps, _, _, _ = metadata # width and height will be taken from stacked tensor

                processed_frames_np = list(frame_generator)

                if not processed_frames_np:
                    raise ValueError(f"No frames extracted from video: {path}")

                images_np_array = np.stack(processed_frames_np, axis=0)
                images = torch.from_numpy(images_np_array)
                
                # Get dimensions from the first frame
                b, h, w, c = images.shape # B is frame_count
                frame_count = b
                file_name = os.path.basename(path).rsplit('.', 1)[0]
                
                return (images, w, h, frame_count, file_name, path, fps)
            
            # Handle GIFs
            elif path.lower().endswith('.gif'):
                gif_generator = process_gif(
                    path, force_rate, image_load_cap, max_res
                )
                metadata = next(gif_generator)
                fps, _, _, _ = metadata # width and height will be taken from stacked tensor

                processed_frames_np = list(gif_generator)

                if not processed_frames_np:
                    # This can happen if GIF was non-animated and yielded 0 frames before metadata
                    # or if image_load_cap was 0 for a non-animated GIF.
                    # The generator itself handles non-animated by yielding 1 frame.
                    # Let's re-check process_gif logic if this error occurs.
                    # For now, assume list has items if generator didn't raise error.
                    if os.path.getsize(path) > 0 : # Check if file has content
                         # if it's a single frame gif, it should have been handled by the gen.
                         # if it's animated and no frames, then it's an issue.
                         # The new _process_gif_generator handles single frame gifs correctly by yielding one frame.
                         # So if processed_frames_np is empty here, it is likely an issue.
                         raise ValueError(f"No frames extracted from GIF: {path}. It might be empty or corrupt.")
                    else: # File is empty
                        raise ValueError(f"GIF file is empty: {path}")


                images_np_array = np.stack(processed_frames_np, axis=0)
                images = torch.from_numpy(images_np_array)
                
                b, h, w, c = images.shape # B is frame_count
                frame_count = b
                file_name = os.path.basename(path).rsplit('.', 1)[0]
                
                return (images, w, h, frame_count, file_name, path, fps)
            
            # Handle archives (zip, tar, 7z)
            elif path.lower().endswith(('.zip', '.tar', '.tar.gz', '.tar.bz2', '.7z')):
                return self.load_from_archive(path, image_load_cap, max_res, sort)
            
            # Handle single image
            else:
                image = load_single_image(path, max_res)
                _, c, h, w = image.shape
                file_name = os.path.basename(path).rsplit('.', 1)[0]
                
                return (image, w, h, 1, file_name, path, 0.0)
                
        except Exception as e:
            logger.error(f"Error loading media: {e}")
            raise
    
    def process_image_list(self, image_paths: List[str], image_load_cap: int = 0, 
                          max_res: int = 0, sort: str = "None") -> Tuple:
        """Process a list of image paths."""
        if not image_paths:
            raise ValueError("No image paths provided")
        
        # Apply sorting
        if sort == "alphabetical":
            image_paths.sort(key=lambda x: x.lower())
        elif sort == "date_created":
            image_paths.sort(key=lambda x: os.path.getctime(x))
        elif sort == "date_modified":
            image_paths.sort(key=lambda x: os.path.getmtime(x))
        elif sort == "random":
            random.seed(0)  # Fixed seed for reproducibility
            random.shuffle(image_paths)
        
        # Apply image_load_cap
        if image_load_cap > 0:
            image_paths = image_paths[:image_load_cap]
        
        # Load all images
        frames = []
        for img_path in image_paths:
            try:
                tensor = load_single_image(img_path, max_res)
                frames.append(tensor)
            except Exception as e:
                logger.warning(f"Failed to load image {img_path}: {e}")
        
        if not frames:
            raise ValueError("No valid images found in the provided paths")
        
        # Concatenate frames
        images = concat_image_tensors(frames)
        
        # Get dimensions from the first frame
        _, c, h, w = images.shape
        parent_directory = os.path.dirname(image_paths[0])
        file_names = [os.path.basename(p).rsplit('.', 1)[0] for p in image_paths]
        file_name = "|".join(file_names[:3]) + ("..." if len(file_names) > 3 else "")
        
        return (images, w, h, len(frames), file_name, parent_directory, 0.0)
    
    def load_from_directory(self, directory: str, image_load_cap: int = 0, 
                           max_res: int = 0, sort: str = "None") -> Tuple:
        """Load images from a directory."""
        # Get all image files
        image_extensions = ['.jpg', '.jpeg', '.png', '.webp', '.gif']
        image_files = []
        
        for ext in image_extensions:
            image_files.extend(glob.glob(os.path.join(directory, f"*{ext}")))
            image_files.extend(glob.glob(os.path.join(directory, f"*{ext.upper()}")))
        
        if not image_files:
            raise ValueError(f"No valid image files found in directory {directory}")
        
        # Process the image list
        return self.process_image_list(image_files, image_load_cap, max_res, sort)
    
    def load_from_archive(self, archive_path: str, image_load_cap: int = 0, 
                         max_res: int = 0, sort: str = "None") -> Tuple:
        """Extract and load images from an archive file."""
        # Create temporary directory
        with tempfile.TemporaryDirectory() as temp_dir:
            # Extract archive
            if archive_path.lower().endswith('.zip'):
                with zipfile.ZipFile(archive_path, 'r') as z:
                    z.extractall(temp_dir)
            elif archive_path.lower().endswith('.7z'):
                with py7zr.SevenZipFile(archive_path, mode='r') as z:
                    z.extractall(path=temp_dir)
            else:  # tar, tar.gz, tar.bz2
                with tarfile.open(archive_path, 'r') as t:
                    t.extractall(temp_dir)
            
            # Check if there's a single directory in the extracted content
            contents = os.listdir(temp_dir)
            if len(contents) == 1 and os.path.isdir(os.path.join(temp_dir, contents[0])):
                temp_dir = os.path.join(temp_dir, contents[0])
            
            # Load from the directory
            result = self.load_from_directory(temp_dir, image_load_cap, max_res, sort)
            
            # Update file path to original archive
            images, w, h, count, _, _, fps = result
            file_name = os.path.basename(archive_path).rsplit('.', 1)[0]
            
            return (images, w, h, count, file_name, archive_path, fps)

class Eden_Save_Param_Dict:
    """Node that collects various inputs, assigns keys to them, and saves them as a JSON file"""
    
    def __init__(self):
        self.output_dir = folder_paths.get_output_directory()
    
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "save_path": ("STRING", {"default": "params.json", "multiline": False}),
            },
            "optional": {
                "key_1": ("STRING", {"default": "param1"}),
                "value_1": (any_typ,),
                "key_2": ("STRING", {"default": "param2"}),
                "value_2": (any_typ,),
                "key_3": ("STRING", {"default": "param3"}),
                "value_3": (any_typ,),
                "key_4": ("STRING", {"default": "param4"}),
                "value_4": (any_typ,),
                "key_5": ("STRING", {"default": "param5"}),
                "value_5": (any_typ,),
                "key_6": ("STRING", {"default": "param6"}),
                "value_6": (any_typ,),
                "key_7": ("STRING", {"default": "param7"}),
                "value_7": (any_typ,),
                "key_8": ("STRING", {"default": "param8"}),
                "value_8": (any_typ,),
                "key_9": ("STRING", {"default": "param9"}),
                "value_9": (any_typ,),
                "key_10": ("STRING", {"default": "param10"}),
                "value_10": (any_typ,),
            }
        }

    FUNCTION = "make_dict"
    RETURN_TYPES = ("STRING", "STRING")
    RETURN_NAMES = ("saved_path", "json_string")
    CATEGORY = "Eden 🌱/Logic"
    DESCRIPTION = "Collects various inputs with custom keys and saves them as a JSON file in the output directory"
    
    def _should_preserve_as_list(self, key, obj):
        """Determine if an object should be preserved as a list rather than joined"""
        # Check for keywords that suggest we should keep as a list
        list_keywords = ["images", "files", "paths", "styles", "inputs", "sources"]
        if any(keyword in key.lower() for keyword in list_keywords):
            return True
        return False
    
    def _is_file_path(self, value):
        """Check if a string looks like a file path with an extension"""
        if not isinstance(value, str):
            return False
        # Check for file extension pattern
        return bool(re.search(r'\.\w+$', value))
    
    def _make_serializable(self, obj, key=""):
        """Convert objects to serializable formats, preserving numeric types and lists when needed"""
        # Handle basic types
        if isinstance(obj, bool):
            return obj
        elif isinstance(obj, int):
            return obj
        elif isinstance(obj, float):
            # Preserve full float precision
            return obj
        elif obj is None:
            return None
        # Handle strings
        elif isinstance(obj, str):
            return obj
        # Handle torch tensors
        elif isinstance(obj, torch.Tensor):
            # Single value tensors convert to actual numbers
            if obj.numel() == 1:
                value = obj.item()
                return value  # Will be int or float automatically
            # For larger tensors but not huge, convert to list
            elif obj.numel() < 1000:
                return obj.tolist()
            # For huge tensors, just return shape info
            else:
                return f"Tensor with shape {obj.shape}"
        # Handle numpy arrays
        elif isinstance(obj, np.ndarray):
            # Single value arrays convert to actual numbers
            if obj.size == 1:
                value = obj.item()
                return value  # Will be int or float automatically
            # For larger arrays but not huge, convert to list
            elif obj.size < 1000:
                return obj.tolist()
            # For huge arrays, just return shape info
            else:
                return f"Array with shape {obj.shape}"
        # Handle lists and tuples
        elif isinstance(obj, (list, tuple)):
            # Check if it's a list of strings
            if all(isinstance(item, str) for item in obj):
                # If this key suggests file paths or images, or list contains file extensions, keep as list
                if self._should_preserve_as_list(key, obj) or any(self._is_file_path(item) for item in obj):
                    return [str(item) for item in obj]  # Keep as list
                # Otherwise join with newlines if multiple strings
                elif len(obj) > 1:
                    return "\n".join(obj)
                elif len(obj) == 1:
                    return obj[0]
                else:
                    return ""
            # Otherwise, process each item normally
            return [self._make_serializable(item, key) for item in obj]
        # Handle dictionaries
        elif isinstance(obj, dict):
            return {str(k): self._make_serializable(v, str(k)) for k, v in obj.items()}
        # Handle other types
        else:
            # Try to extract basic properties
            try:
                props = {}
                for attr in dir(obj):
                    if not attr.startswith('_') and not callable(getattr(obj, attr)):
                        props[attr] = self._make_serializable(getattr(obj, attr), attr)
                if not props: # If no public attributes, just return string representation
                    return str(obj)
                return {"_type": type(obj).__name__, "properties": props}
            except:
                return str(obj)
    
    def _process_filename_prefix(self, filename_prefix):
        """Process date formatters and other variables in the filename prefix"""
        # Process date formatters
        date_regex = r"%date:([^%]+)%"
        date_matches = re.findall(date_regex, filename_prefix)
        for date_format in date_matches:
            date_str = datetime.now().strftime(date_format)
            filename_prefix = filename_prefix.replace(f"%date:{date_format}%", date_str)
        
        return filename_prefix
    
    def _get_unique_filename(self, filename_prefix):
        """Generate a unique filename that doesn't overwrite existing files"""
        # Ensure .json extension
        if not filename_prefix.lower().endswith('.json'):
            filename_prefix += '.json'
        
        # Process any formatters in the filename
        filename_prefix = self._process_filename_prefix(filename_prefix)
        
        # Extract base path and file extension
        base_name, ext = os.path.splitext(filename_prefix)
        
        # Get output directory and create if needed
        output_dir = self.output_dir
        os.makedirs(output_dir, exist_ok=True)
        
        # Check for subfolder in the path
        subfolder = ""
        if os.path.dirname(base_name):
            subfolder = os.path.dirname(base_name)
            output_dir = os.path.join(output_dir, subfolder)
            os.makedirs(output_dir, exist_ok=True)
            base_name = os.path.basename(base_name)
        
        # Find a unique counter value to avoid overwriting
        counter = 1
        while True:
            filename = f"{base_name}_{counter:05}{ext}"
            full_path = os.path.join(output_dir, filename)
            if not os.path.exists(full_path):
                break
            counter += 1
        
        return full_path, filename, subfolder
    
    def make_dict(self, save_path, **kwargs):
        """Combine all inputs into a dictionary and save to JSON"""
        result_dict = {}
        
        try:
            # Process all key-value pairs
            for i in range(1, 11):
                key_name = f"key_{i}"
                value_name = f"value_{i}"
                
                # Check if this pair exists in kwargs
                if key_name in kwargs and value_name in kwargs:
                    key = kwargs[key_name]
                    value = kwargs[value_name]
                    
                    # Only add if we have both key and value
                    if key and value is not None:
                        try:
                            # Pass the key to the serializer so it can make context-aware decisions
                            result_dict[key] = self._make_serializable(value, key)
                        except Exception as e:
                            print(f"Error processing {key}: {e}")
                            result_dict[key] = f"ERROR: {str(e)}"
            
            # Generate a unique filename
            full_path, filename, subfolder = self._get_unique_filename(save_path)
            
            # Create JSON string with full precision for floats
            json_string = json.dumps(result_dict, indent=2, ensure_ascii=False)
            
            # Save to file
            with open(full_path, 'w') as f:
                f.write(json_string)
            
            print(f"Saved parameter dictionary to {full_path}")
            return (full_path, json_string)
            
        except Exception as e:
            print(f"Error in Eden_Save_Param_Dict: {e}")
            return (f"ERROR: {str(e)}", "{}")
