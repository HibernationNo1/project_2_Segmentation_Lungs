import tensorflow as tf
import numpy as np


import skimage.transform
import math
import warnings
import scipy
import json


from distutils.version import LooseVersion

# image의 lung부분의 pixel값에 normal distribution값 만큼을 빼는 preprocessing
def preprocessing_sub_ND(img_):
	mu = 0.5
	sigma = 0.35
	distri_img = img_.copy()

	x = distri_img[distri_img < 0.6].copy()
	y = (1 / np.sqrt(2 * np.pi * sigma**2)) * np.exp(-(x-mu)**2 / (2 * sigma**2))	
	distri_img[distri_img < 0.6] = distri_img[distri_img < 0.6] -  y/6

	return distri_img

def preprocessing_HE(img_):
    hist, _ = np.histogram(img_.flatten(), 256,[0,256])		# histogram
    cdf = hist.cumsum()										# 누적합
    cdf_m = np.ma.masked_equal(cdf,0)						# 0인 element는 mask처리
    cdf_m = (cdf_m - cdf_m.min())*255/(cdf_m.max()-cdf_m.min()) # Histogram equalization
    cdf = np.ma.filled(cdf_m,0).astype('uint8')				# np.ma.masked_equal로 인해 mask처리된 element를 0으로 
    img_2 = cdf[img_]										# original image에 historam적용
    
    return img_2  

def resize(image, output_shape, order=1, mode='constant', cval=0, clip=True,
           preserve_range=False, anti_aliasing=False, anti_aliasing_sigma=None):
    """A wrapper for Scikit-Image resize().
    Scikit-Image generates warnings on every call to resize() if it doesn't
    receive the right parameters. The right parameters depend on the version
    of skimage. This solves the problem by using different parameters per
    version. And it provides a central place to control resizing defaults.
    """

    if LooseVersion(skimage.__version__) >= LooseVersion("0.14"):
        # New in 0.14: anti_aliasing. Default it to False for backward
        # compatibility with skimage 0.13.
        return skimage.transform.resize(
            image, output_shape,
            order=order, mode=mode, cval=cval, clip=clip,
            preserve_range=preserve_range, anti_aliasing=anti_aliasing,
            anti_aliasing_sigma=anti_aliasing_sigma)
    else:
        return skimage.transform.resize(
            image, output_shape,
            order=order, mode=mode, cval=cval, clip=clip,
            preserve_range=preserve_range)
	


def unmold_mask(mask, bbox, image_shape):
    """Converts a mask generated by the neural network to a format similar
    to its original shape.
    mask: [height, width] of type float. A small, typically 28x28 mask.
    bbox: [y1, x1, y2, x2]. The box to fit the mask in.
    Returns a binary mask with the same size as the original image.
    """
    threshold = 0.5
    y1, x1, y2, x2 = bbox
    mask = resize(mask, (y2 - y1, x2 - x1))
    mask = np.where(mask >= threshold, 1, 0).astype(np.bool)

    # Put the mask in the right location.
    full_mask = np.zeros(image_shape[:2], dtype=np.bool)
    full_mask[y1:y2, x1:x2] = mask
    return full_mask

def denorm_boxes(boxes, shape):
	"""
	Converts boxes from normalized coordinates to pixel coordinates.
	boxes: [N, (y1, x1, y2, x2)] in normalized coordinates
	shape: [..., (height, width)] in pixels
	Note: In pixel coordinates (y2, x2) is outside the box. But in normalized
	coordinates it's inside the box.
	Returns:
		[N, (y1, x1, y2, x2)] in pixel coordinates
	"""
	h, w = shape
	scale = np.array([h - 1, w - 1, h - 1, w - 1])
	shift = np.array([0, 0, 1, 1])
	return np.around(np.multiply(boxes, scale) + shift).astype(np.int32)


def extract_bboxes(mask):
    """
	Compute bounding boxes from masks.
    mask: [height, width, num_instances]. Mask pixels are either 1 or 0.
    Returns: bbox array [num_instances, (y1, x1, y2, x2)].
    """
    boxes = np.zeros([mask.shape[-1], 4], dtype=np.int32)
    for i in range(mask.shape[-1]):
        m = mask[:, :, i]
        # Bounding box.
        horizontal_indicies = np.where(np.any(m, axis=0))[0]
        vertical_indicies = np.where(np.any(m, axis=1))[0]
        if horizontal_indicies.shape[0]:
            x1, x2 = horizontal_indicies[[0, -1]]
            y1, y2 = vertical_indicies[[0, -1]]
            # x2 and y2 should not be part of the box. Increment by 1.
            x2 += 1
            y2 += 1
        else:
            # No mask for this instance. Might happen due to
            # resizing or cropping. Set bbox to zeros
            x1, x2, y1, y2 = 0, 0, 0, 0
        boxes[i] = np.array([y1, x1, y2, x2])
    return boxes.astype(np.int32)

def norm_boxes(boxes, shape):
	"""
	Converts boxes from pixel coordinates to normalized coordinates.
	boxes: [N, (y1, x1, y2, x2)] in pixel coordinates
	shape: [..., (height, width)] in pixels
	
	Note: In pixel coordinates (y2, x2) is outside the box. But in normalized
	coordinates it's inside the box.
	
	Returns:
		[N, (y1, x1, y2, x2)] in normalized coordinates
	"""
	
	h, w = shape
	scale = np.array([h - 1, w - 1, h - 1, w - 1])
	shift = np.array([0, 0, 1, 1])
	return np.divide((boxes - shift), scale).astype(np.float32)

import tensorflow.keras.backend as K
def norm_boxes_graph2(x):
	"""
	x = [input_gt_boxes, input_image]
	"""
	boxes, tensor_for_shape = x
	shape = K.shape(tensor_for_shape)[1:3]
	return norm_boxes_graph(boxes,shape)

def norm_boxes_graph(boxes, shape):
	"""
	Converts boxes from pixel coordinates to normalized coordinates
	boxes: [batch, MAX_GT_INSTANCES, 4] in pixel coordinates
		4 : (y1, x1, y2, x2)
	shape: [2] in pixels
		2 : (height, width)

	Note: In pixel coordinates (y2, x2) is outside the box. But in normalized
	coordinates it's inside the box.
	
	Returns:
		[..., (y1, x1, y2, x2)] in normalized coordinates
	"""

	# image_shape = (256, 256, 3)일 때 
	# scale : [255. 255. 255. 255.] tensor

	h, w = tf.split(tf.cast(shape, tf.float32), 2)
	scale = tf.concat([h, w, h, w], axis=-1) - tf.constant(1.0)
	shift = tf.constant([0., 0., 1., 1.])
	result = tf.divide(boxes - shift, scale)
	return result


def clip_boxes_graph(boxes, window):
	"""
	boxes: [N, (y1, x1, y2, x2)]
	window: [4] in the form y1, x1, y2, x2
	
	Return : [N, (y1, x1, y2, x2)]
	"""
	
	# Split
	wy1, wx1, wy2, wx2 = tf.split(window, 4)
	y1, x1, y2, x2 = tf.split(boxes, 4, axis=1)
	
	# Clip
	y1 = tf.maximum(tf.minimum(y1, wy2), wy1)
	x1 = tf.maximum(tf.minimum(x1, wx2), wx1)
	y2 = tf.maximum(tf.minimum(y2, wy2), wy1)
	x2 = tf.maximum(tf.minimum(x2, wx2), wx1)
	clipped = tf.concat([y1, x1, y2, x2], axis=1, name="clipped_boxes")
	clipped.set_shape((clipped.shape[0], 4))
	return clipped
		

def box_refinement_graph(box, gt_box):
	"""
	box를 gt_box의 좌표에 맞추도록 하는 변환값(delta)을 계산
	box : [N, (y1, x1, y2, x2)]
	gt_box : [N, (y1, x1, y2, x2)]
	
	Return : 
		result : [N, (y1, x1, y2, x2)]
	"""
	
	box = tf.cast(box, tf.float32)
	gt_box = tf.cast(gt_box, tf.float32)
	
	height = box[:, 2] - box[:, 0]
	width = box[:, 3] - box[:, 1]
	center_y = box[:, 0] + 0.5 * height
	center_x = box[:, 1] + 0.5 * width
	
	gt_height = gt_box[:, 2] - gt_box[:, 0]
	gt_width = gt_box[:, 3] - gt_box[:, 1]
	gt_center_y = gt_box[:, 0] + 0.5 * gt_height
	gt_center_x = gt_box[:, 1] + 0.5 * gt_width
	dy = (gt_center_y - center_y) / height
	dx = (gt_center_x - center_x) / width
	dh = tf.math.log(gt_height / height)
	dw = tf.math.log(gt_width / width)
	
	result = tf.stack([dy, dx, dh, dw], axis=1)
	return result

def batch_slice(inputs, graph_fn, batch_size, names=None):
	"""
	input을 여러 조각으로 나눈 후 각 function의 input으로 넣고 각각의 output을 결합
	inputs: list of tensors. All must have the same first dimension length
	graph_fn: A function that returns a TF tensor that's part of a graph.
		lambda x, y: tf.gather(x, y)
		lambda x, y: apply_box_deltas_graph(x, y)
		lambda x: clip_boxes_graph(x, window)
		nms
		lambda w, x, y, z: detection_targets_graph
		lambda x, y, w, z: refine_detections_graph(x, y, w, z, self.config)
	batch_size: number of slices to divide the data into. # IMAGES_PER_GPU = 2
	names: If provided, assigns names to the resulting tensors.
	"""
		
	if not isinstance(inputs, list):    # inputs이 list가 아니라면
		inputs = [inputs]
			
	outputs = list()
	for i in range(batch_size): # batch number에 따라 각 input을 조각
		inputs_slice = [x[i] for x in inputs]   # [x1[i], x2[i], ..]
		output_slice = graph_fn(*inputs_slice)  
		if not isinstance(output_slice, (tuple, list)):
			output_slice = [output_slice]
		outputs.append(output_slice)
		
	# graph_fn == lambda x, y: tf.gather(x, y) 기준 len(outputs) == batch_size
		
	# 각 element가 outputs의 list인 list type에서
	# slices된 list를 elements로 갖는 output가 하나의 element인 list type으로 변경
	# graph_fn == lambda x, y: tf.gather(x, y) 기준 len(outputs) == 1
	outputs = list(zip(*outputs))
	
	if names is None:
		names = [None] * len(outputs)
		
	result = [tf.stack(o, axis=0, name=n)
			for o, n in zip(outputs, names)]
	if len(result) == 1:
		result = result[0]
	return result

def apply_box_deltas_graph(boxes, deltas):
    """
    Applies the given deltas to the given boxes.
    boxes: [N, (y1, x1, y2, x2)]
    deltas: [N, (dy, dx, dh, dw)] refinements to apply
    
    Return : [N, (y1, x1, y2, x2)]
    """
    
    # Convert to y, x, h, w
    height = boxes[:, 2] - boxes[:, 0]
    width = boxes[:, 3] - boxes[:, 1]
    center_y = boxes[:, 0] + 0.5 * height
    center_x = boxes[:, 1] + 0.5 * width
    
    # Apply deltas
    center_y += deltas[:, 0] * height
    center_x += deltas[:, 1] * width
    height *= tf.exp(deltas[:, 2])
    width *= tf.exp(deltas[:, 3])
    
    # Convert back to y1, x1, y2, x2
    y1 = center_y - 0.5 * height
    x1 = center_x - 0.5 * width
    y2 = y1 + height
    x2 = x1 + width
    
    result = tf.stack([y1, x1, y2, x2], axis=1, name="apply_box_deltas_out")
    return result


def load_dataset(ratio, path_dataset):
	"""
	load dataset and split train, validation 

	ratio : ratio of training data in the dataset 
	path_dataset : path of dataset to load
	"""

	training_data_ratio = ratio
	with open(path_dataset) as json_file:
		dataset = json.load(json_file)
		
	num_train_data = round(len(dataset) * training_data_ratio)

	dataset_train = dataset[:num_train_data]
	dataset_validation = dataset[num_train_data:]
	return dataset_train, dataset_validation


def compute_iou(box, boxes, box_area, boxes_area):
	"""
	Calculates IoU of the given box with the array of the given boxes.
	box: 1D vector, [y1, x1, y2, x2]
	boxes: [boxes_count, (y1, x1, y2, x2)]
	box_area: float. the area of 'box'   [area]
	boxes_area: array of length boxes_count.  [boxes_count, area]
    
	"""
    
	# Calculate intersection areas
	y1 = np.maximum(box[0], boxes[:, 0])
	y2 = np.minimum(box[2], boxes[:, 2])
	x1 = np.maximum(box[1], boxes[:, 1])
	x2 = np.minimum(box[3], boxes[:, 3])
	intersection_areas = np.maximum(x2 - x1, 0) * np.maximum(y2 - y1, 0)
	union = box_area + boxes_area[:] - intersection_areas[:]
	iou = intersection_areas / union
	return iou


def compute_overlaps(anchors, gt_boxes):
	"""
	Computes IoU overlaps between two sets of boxes.
	anchors : [anchor_count, (y1, x1, y2, x2)]
	gt_boxes : [instance_count, (y1, x1, y2, x2)]
	
	Return [anchor_count, number of IOU equal to instance_count]
		overlaps: 
	"""
	boxes1, boxes2 =  anchors, gt_boxes
     
	area1 = (boxes1[:, 2] - boxes1[:, 0]) * (boxes1[:, 3] - boxes1[:, 1])
	area2 = (boxes2[:, 2] - boxes2[:, 0]) * (boxes2[:, 3] - boxes2[:, 1])
    
	# Compute overlaps to generate matrix [boxes1 count, boxes2 count]
	# Each cell contains the IoU value.
	overlaps = np.zeros((boxes1.shape[0], boxes2.shape[0])) 
	for i in range(overlaps.shape[1]):	# instance_count
		box2 = boxes2[i]				# (y1, x1, y2, x2)
		overlaps[:, i] = compute_iou(box2, boxes1, area2[i], area1)
	return overlaps	



def compose_image_meta(image_id, original_image_shape, image_shape,
                       window, scale, active_class_ids):
	"""
	image_id : index of image	
	original_shape : [H, W, C] before resizing or padding.	# [1024, 1024, 3]
	image_shape: [H, W, C] after resizing and padding	# [256, 256, 3]
	window: (y1, x1, y2, x2) in pixels. The area of the image where the real 
    		image is (excluding the padding)	# (192, 192, 832, 832)
	scale: The scaling factor applied to the original image (float32)	# 2.5
	active_class_ids: [num_instances] 
		num_instances = 2일 때 active_class_ids == [1, 1]
	"""

	meta = np.array(
		[image_id] +					# size=1
		list(original_image_shape)	+	# size=3
		list(image_shape) + 			# size=3
		list(window) +					# size=4
		[scale] +						# size=1
		list(active_class_ids) 				# size=num_classes  # 2
		)
	
	return meta


def resize_mask(mask, scale, padding, crop=None):
	"""Resizes a mask using the given scale and padding.
	Typically, you get the scale and padding from resize_image() to
	ensure both, the image and the mask, are resized consistently.
    
	scale: mask scaling factor
	padding: Padding to add to the mask in the form
			[(top, bottom), (left, right), (0, 0)]
	"""
	with warnings.catch_warnings():
		warnings.simplefilter("ignore")	# 경고 비활성화
		mask = scipy.ndimage.zoom(mask, zoom=[scale, scale, 1], order=0)
	if crop is not None:	# 해당없음
		y, x, h, w = crop
		mask = mask[y:y + h, x:x + w]
	else:
		mask = np.pad(mask, padding, mode='constant', constant_values=0)
			
	return mask

def mold_image(images, config):
	"""
	Expects an RGB image (or array of images) and subtracts
	the mean pixel and converts it to float. Expects image
	colors in RGB order.
	"""
	return images.astype(np.float32) - config.MEAN_PIXEL

def resize_image(image, mode = None, min_dim=None, max_dim=None, min_scale=None):
	"""
	min_dim : image를 줄이기를 결정했을 때 사용. 
	max_dim : image를 늘리기를 결정했을 때 사용. 
	min_scale : if provided, image가 min_scale의 비율로 확대되는지 확인

	Returns:
		image: the resized image
		window: (y1, x1, y2, x2).
			max_dim으로 인해 image가 커진다면 zeropadding이 추가된다. 
			이 때 window의 각 coordinate는 padding을 제외한 image부분의 coordinate이다.
		scale: The scale factor used to resize the image
		padding: Padding added to the image [(top, bottom), (left, right), (0, 0)]
	"""
	# Keep track of image dtype and return results in the same dtype
	image_dtype = image.dtype

	# Default window (y1, x1, y2, x2) and default scale == 1.
	h, w = image.shape[:2]
	window = (0, 0, h, w)
	scale = 1
	padding = [(0, 0), (0, 0), (0, 0)]
	crop = None
    
	if mode == "none":	
		return image, window, scale, padding, crop
    
	# input image가 min_dim보다도 작을 때 scale조정 
	# min_dim = 640, h=w=256 		:  scale = 2.5
	if min_dim:
		# Scale up but not down
		scale = max(1, min_dim / min(h, w))
	if min_scale and scale < min_scale:
		scale = min_scale
	
	
    
	# input image가 square이 아닌 경우 square로 resize할 때 scale조정.
	if max_dim and mode == "square": 
		image_max = max(h, w)
		if round(image_max * scale) > max_dim:
			scale = max_dim / image_max


	if scale != 1:
		image = resize(image, (round(h * scale), round(w * scale)),
					preserve_range=True)


	if mode == "square":
		# Get new height and width
		# zero padding 으로 shape 맞춰줌 (input data에는 크게 의미 없음)
		h, w = image.shape[:2]
		top_pad = (max_dim - h) // 2
		bottom_pad = max_dim - h - top_pad
		left_pad = (max_dim - w) // 2
		right_pad = max_dim - w - left_pad
		padding = [(top_pad, bottom_pad), (left_pad, right_pad), (0, 0)]
		image = np.pad(image, padding, mode='constant', constant_values=0)
		window = (top_pad, left_pad, h + top_pad, w + left_pad)
	else:
		raise Exception("Mode {} not supported".format(mode))
	
	# image.shape = (256, 256, 3)
	# window = 0, 0, 256, 256
      
	return image.astype(image_dtype), window, scale, padding, crop


# The strides of each layer of the FPN Pyramid
def compute_backbone_shapes(config, image_shape):
	"""
	image_shape : shape of input
	"""
	# Currently supports ResNet only
	assert config.BACKBONE in ["resnet50", "resnet101"]
	backbone_shapes = np.array([
			[int(math.ceil(image_shape[0] / stride)),
			int(math.ceil(image_shape[1] / stride))]
			for stride in config.BACKBONE_STRIDES])
	return backbone_shapes


def generate_anchors(anchor_scale, anchor_ratios, 
					 feature_shape, feature_stride, anchor_stride):
	"""
	anchor_scale : 1D array of anchor sizes in pixels. Example: [32, 64, 128]
	anchor_ratios : 1D array of anchor ratios of width/height. Example: [0.5, 1, 2]
	shape: [height, width] spatial shape of the feature map over which
			to generate anchors
	feature_stride: Stride of the feature map relative to the image in pixels.
	anchor_stride: Stride of anchors on the feature map.
	"""

	# anchor_scale * anchor_ratio의 모든 경우의 수 
	anchor_scale, anchor_ratios = np.meshgrid(np.array(anchor_scale), np.array(anchor_ratios))
	anchor_scale = anchor_scale.flatten()  	# [anchor_scale, anchor_scale, anchor_scale]
	anchor_ratios = anchor_ratios.flatten() # [0.5, 1, 2] == anchor_ratio
    
	# anchor의 ratio에 따른 각각의 w, h
	widths = anchor_scale * np.sqrt(anchor_ratios)
	heights = anchor_scale / np.sqrt(anchor_ratios)
    
	# anchor가 image위에서 sliding하는 x, y범위
	shifts_y = np.arange(0, feature_shape[0], anchor_stride) * feature_stride
	shifts_x = np.arange(0, feature_shape[1], anchor_stride) * feature_stride
	shifts_x, shifts_y = np.meshgrid(shifts_x, shifts_y)
	
	# 각 pixel 위치에서의 x, y, w, h
	box_widths, box_centers_x = np.meshgrid(widths, shifts_x)
	box_heights, box_centers_y = np.meshgrid(heights, shifts_y)
    
	# Reshape to get a list of (y, x) and a list of (h, w)
	box_centers = np.stack([box_centers_y, box_centers_x], axis=2).reshape([-1, 2])
	box_sizes  = np.stack([box_heights, box_widths], axis=2).reshape([-1, 2])
	# feature_strides = 32 기준 box_y_x_centers.shape == box_h_w.shape : (196608, 2)

	# Convert to corner coordinates (y1, x1, y2, x2)
	anchor_boxes = np.concatenate([box_centers - 0.5 * box_sizes,
                            	   box_centers + 0.5 * box_sizes], axis=1)
	return anchor_boxes



def generate_pyramid_anchors(anchor_scales, anchor_ratio, 
							 feature_shapes, feature_strides, anchor_stride):
	"""
	anchor_scales = RPN_ANCHOR_SCALES
	anchor_ratio = RPN_ANCHOR_RATIOS
	feature_shape : [[256 256], [128, 128], [64,  64], [32,  32], [16,  16]]
		backbone_shapes from `compute_backbone_shapes`
	feature_strides = BACKBONE_STRIDES
	anchor_stride = RPN_ANCHOR_STRIDE 
    
	Return : [anchor_counts, (y1, x1, y2, x2)]
	"""
	anchors = list()
	for i in range(len(anchor_scales)):
		anchor_boxes = generate_anchors(anchor_scales[i], anchor_ratio, feature_shapes[i],
                                        feature_strides[i], anchor_stride)
		anchors.append(anchor_boxes)
        
	return np.concatenate(anchors, axis=0)