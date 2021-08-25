import segmentation_models as sm
import glob
import cv2
import sys
import matplotlib.pyplot as plt
import numpy as np

from scipy import ndimage
from scipy.ndimage import label


from absl import app

import os
os.environ["CUDA_VISIBLE_DEVICES"] = "1"

# change framework of sm from keras to tensorflow.keras
sm.set_framework('tf.keras')

IMAGE_SIZE = (256,256,3)	# original size (512, 512, 3)

# Parameter
path_base_model = os.path.join(os.getcwd() , 'models')
path_base_input = os.path.join(os.getcwd() , 'dataset')  
path_base_result = os.path.join(os.getcwd() , 'result')
os.makedirs(path_base_result, exist_ok=True)  

path_save_mask_img = os.path.join(path_base_result , 'result_mask') # instance for save of mask image 
os.makedirs(path_save_mask_img, exist_ok=True)

path_save_comp_img = os.path.join(path_base_result , 'result_distinguish') # instance for save of distinguish image 
os.makedirs(path_save_comp_img, exist_ok=True)

# Model loads
BACKBONE = 'efficientnetb0'
model1 = sm.Unet(BACKBONE, input_shape = (IMAGE_SIZE[0],IMAGE_SIZE[1],IMAGE_SIZE[2]),classes=1, activation='sigmoid',encoder_weights='imagenet')
model2 = sm.Unet(BACKBONE, input_shape = (IMAGE_SIZE[0],IMAGE_SIZE[1],IMAGE_SIZE[2]),classes=1, activation='sigmoid',encoder_weights='imagenet')
model3 = sm.Unet(BACKBONE, input_shape = (IMAGE_SIZE[0],IMAGE_SIZE[1],IMAGE_SIZE[2]),classes=1, activation='sigmoid',encoder_weights='imagenet')

BACKBONE = 'efficientnetb7'
model4 = sm.Unet(BACKBONE, input_shape = (IMAGE_SIZE[0],IMAGE_SIZE[1],IMAGE_SIZE[2]),classes=1, activation='sigmoid',encoder_weights='imagenet')
model5 = sm.Unet(BACKBONE, input_shape = (IMAGE_SIZE[0],IMAGE_SIZE[1],IMAGE_SIZE[2]),classes=1, activation='sigmoid',encoder_weights='imagenet')

preprocess_input = sm.get_preprocessing(BACKBONE)

# load pre-trained model weights 
model1.load_weights(path_base_model + '\model1.hdf5')
model2.load_weights(path_base_model + '\model2.hdf5')
model3.load_weights(path_base_model + '\model3.hdf5')
model4.load_weights(path_base_model + '\model4.hdf5')
model5.load_weights(path_base_model + '\model5.hdf5')

# Histogram Equalization
def preprocessing_HE(img_):
    hist, _ = np.histogram(img_.flatten(), 256,[0,256])		# histogram
    cdf = hist.cumsum()										# 누적합
    cdf_m = np.ma.masked_equal(cdf,0)						# 0인 element는 mask처리
    cdf_m = (cdf_m - cdf_m.min())*255/(cdf_m.max()-cdf_m.min()) # Histogram equalization
    cdf = np.ma.filled(cdf_m,0).astype('uint8')				# np.ma.masked_equal로 인해 mask처리된 element를 0으로 
    img_2 = cdf[img_]										# original image에 historam적용
    
    return img_2  
        
def get_binary_mask(mask_, th_ = 0.5):
    mask_[mask_>th_]  = 1
    mask_[mask_<=th_] = 0
    return mask_
    
def ensemble_results(mask1_, mask2_, mask3_, mask4_, mask5_):
    # predicted mask image의 element가 0.5보다 높으면 1, 같거나 낮으면 0
    mask1_ = get_binary_mask(mask1_)
    mask2_ = get_binary_mask(mask2_)
    mask3_ = get_binary_mask(mask3_)
    mask4_ = get_binary_mask(mask4_)
    mask5_ = get_binary_mask(mask5_)
    
	# 모든 model의 predicted mask image를 합산 후 조건
    ensemble_mask = mask1_ + mask2_ + mask3_ + mask4_ + mask5_
    ensemble_mask[ensemble_mask<=2.0] = 0
    ensemble_mask[ensemble_mask> 2.0] = 1
    
    return ensemble_mask

def postprocessing_HoleFilling(mask_):
	ensemble_mask_post_temp = ndimage.binary_fill_holes(mask_).astype(int)
	return ensemble_mask_post_temp

def get_maximum_index(labeled_array):
	ind_nums = []
	# objct가 2개라고 할 때 np.unique(labeled_array) == 0, 1, 2
	# ind_num = [[0, 0], [0, 1], [0, 2]]
	for i in range (len(np.unique(labeled_array)) - 1):
		ind_nums.append ([0, i+1])

	# ind_num = [[1번 object인 pixel의 개수, 0], [2번 object인 pixel의 개수, 1], ...
	for i in range (1, len(np.unique(labeled_array))):
		ind_nums[i-1][0] = len(np.where(labeled_array == np.unique(labeled_array)[i])[0])

	ind_nums = sorted(ind_nums)
	
	# pixel의 개수가 가장 많은 object 2개의 number 반환
	return ind_nums[len(ind_nums)-1][1], ind_nums[len(ind_nums)-2][1]
    

def postprocessing_EliminatingIsolation(ensemble_mask_post_temp):
    # 각 obejct에 대해 number를 부여하여 image의 object의 각 pixel마다 number를 곱한다.
	labeled_array, _ = label(ensemble_mask_post_temp)

	# lung으로 가장 유력해 보이는 object의 number 반환
	ind_max1, ind_max2 = get_maximum_index(labeled_array)
    
	# 가장 유력한 object 2개만 따로 추려내서 mask image로 그린다.
	ensemble_mask_post_temp2 = np.zeros(ensemble_mask_post_temp.shape)
	ensemble_mask_post_temp2[labeled_array == ind_max1] = 1
	ensemble_mask_post_temp2[labeled_array == ind_max2] = 1    

	return ensemble_mask_post_temp2.astype(int)


# 추가
def image_resize(img_, IMAGE_SIZE):
	if np.shape(img_)[0] > IMAGE_SIZE[0] and np.shape(img_)[1] > IMAGE_SIZE[1] : # original image가 기대하는 input image보다 작을 때
		# image를 더 큰 size로 resize(Bilinear Interpolation 사용)
		img_resize = cv2.resize(img_,(IMAGE_SIZE[0],IMAGE_SIZE[1]),cv2.INTER_LINEAR)

	else : 	# original image가 기대하는 input image보다 클 때
		# image를 더 작은 size로 resize(Area Interpolation 사용)
		img_resize = cv2.resize(img_,(IMAGE_SIZE[0],IMAGE_SIZE[1]),cv2.INTER_AREA)
	
	return img_resize


def get_prediction(model_, img_, IMAGE_SIZE):  # 수정
	img_resize = image_resize(img_, IMAGE_SIZE)

	img_org_resize_HE = preprocessing_HE(img_resize)    	# Histogram Equalization
	img_ready = preprocess_input(img_org_resize_HE)			# backbone에 알맞게 전처리
	img_ready = np.expand_dims(img_ready, axis=0) 			# (256, 256, 3) → (1, 256, 256, 3)
	pr_mask = model_.predict(img_ready)			# input data에 대해 model이 학습한 parameters를 기반으로 predict
	pr_mask = np.squeeze(pr_mask, axis = 0)
	return pr_mask[:,:,0]


# 추가
def get_lung_color_image(labeled_array, object_num, color):
	labeled_array_temp = np.zeros(labeled_array.shape)
	labeled_array_temp[labeled_array == object_num] = 1

	if color == 'R':
		lung_B = labeled_array_temp * 0
		lung_G = labeled_array_temp * 0
		lung_R = labeled_array_temp * 255
	elif color == 'B':
		lung_B = labeled_array_temp * 255
		lung_G = labeled_array_temp * 0
		lung_R = labeled_array_temp * 0

	image_lung = np.dstack([lung_B, lung_G, lung_R]).astype('uint8')

	return image_lung

# lung의 좌, 우를 구별하고 mask image및 add image를 concatenate
def Separation_l_r_lung(ensemble_mask_post_HF_EI, img_, path_, iter, path_save_comp_img):
	image_left_lung = np.zeros_like(IMAGE_SIZE).astype('uint8')
	image_right_lung = np.zeros_like(IMAGE_SIZE).astype('uint8')
	
	# image resize for addWeighted
	img_resize = image_resize(img_, IMAGE_SIZE)

	labeled_array , feature_num = label(ensemble_mask_post_HF_EI)

	for object_num in range(1, feature_num+1):
		min_index, max_index = IMAGE_SIZE[1], 0

		for i in range(int(IMAGE_SIZE[0])):  					# image의 위에서 아래로 slicing
			# object number와 같은 pixel의 index중 max, min좌표를 통해 left, right 여부 구별
			idx_temp = np.where(labeled_array[i] == object_num)	
			
			if np.shape(idx_temp)[1] !=0:
				max_index = max(max_index, idx_temp[0][-1])
				min_index = min(min_index, idx_temp[0][0])		

			if i == int(IMAGE_SIZE[0])-1:
				# object의 가장 오른쪽 pixel 좌표가 image의 2/3 지점 좌표보다 작고,
				# object의 가장 왼쪽 pixel 좌표가 image의 1/3 지점 좌표보다 작으면 left lung 
				if max_index < int(IMAGE_SIZE[1]*2/3) and min_index < int(IMAGE_SIZE[1]*1/3):   # left lung
					image_left_lung = get_lung_color_image(labeled_array, object_num, 'B')

				elif max_index > int(IMAGE_SIZE[1]*2/3) and min_index > int(IMAGE_SIZE[1]*1/3):	# right lung
					image_right_lung = get_lung_color_image(labeled_array, object_num, 'R')

				else:
					print("Separation failed!")

	color_mask_lung = image_left_lung + image_right_lung

	# adding images by applying transparency
	alpha_img_resize = 0.8		# original image 투명도 
	beta_color_mask_lung = 1-alpha_img_resize
	res_image_lung = cv2.addWeighted(img_resize, alpha_img_resize, color_mask_lung, beta_color_mask_lung, 0)	

	fig, ax = plt.subplots(2, 3, figsize=(12, 12))

	fig.suptitle(str(path_.split('\\')[-1]), fontsize=25, fontweight = 'bold')
	fig.tight_layout()

	ax[0, 1].imshow(img_)
	ax[0, 1].set_title('Input with HE', fontsize = 20)

	ax[1, 0].imshow(ensemble_mask_post_HF_EI, cmap='gray')
	ax[1, 0].set_title('Ensemble + HF + EI', fontsize = 20)

	ax[1, 1].imshow(color_mask_lung)
	ax[1, 1].set_title('Color Ensemble + HF + EI ', fontsize = 20)

	ax[1, 2].imshow(res_image_lung)
	ax[1, 2].set_title('Color + Input Image', fontsize = 20)

	for axis in ax.flat:	# 좌표, 축 삭제(image만 보기 위해)
		axis.get_xaxis().set_visible(False)
		axis.get_yaxis().set_visible(False)
		for _, spine in axis.spines.items():
			spine.set_visible(False)

	plt.savefig(path_save_comp_img + '/result_' + str(iter) +  '.png')
	# plt.show()
	plt.close()


# inference
def main(_):
	# image가 저장된 directory에서 각 image를 가져온다.
	for iter, path_ in enumerate(sorted(glob.glob (path_base_input + '\*.*'))):		 

		print ('file: ', path_.split('\\')[-1])
		
		img = cv2.imread(path_)    
		# input image에 대한 model의 predictor 반환
		pr_mask1 = get_prediction (model1, img, IMAGE_SIZE) 
		pr_mask2 = get_prediction (model2, img, IMAGE_SIZE)
		pr_mask3 = get_prediction (model3, img, IMAGE_SIZE)
		pr_mask4 = get_prediction (model4, img, IMAGE_SIZE)
		pr_mask5 = get_prediction (model5, img, IMAGE_SIZE)    

		# ensemble mask 계산	
		ensemble_mask            = ensemble_results(pr_mask1, pr_mask2, pr_mask3, pr_mask4, pr_mask5)
		
		# mask image의 각 object안의 빈 공간을 채워넣는다.
		ensemble_mask_post_HF    = postprocessing_HoleFilling(ensemble_mask)

		# draw Lung mask image
		ensemble_mask_post_HF_EI = postprocessing_EliminatingIsolation(ensemble_mask_post_HF)

		fig, ax = plt.subplots(3, 3, figsize=(12, 12))
		ax[0, 0].imshow(img)
		ax[0, 0].set_title('Input with HE', fontsize = 20)

		ax[0, 1].imshow(pr_mask1, cmap='gray')
		ax[0, 1].set_title('Model 1', fontsize = 20)

		ax[0, 2].imshow(pr_mask2, cmap='gray')
		ax[0, 2].set_title('Model 2', fontsize = 20)

		ax[1, 0].imshow(pr_mask3, cmap='gray')
		ax[1, 0].set_title('Model 3', fontsize = 20)

		ax[1, 1].imshow(pr_mask4, cmap='gray')
		ax[1, 1].set_title('Model 4', fontsize = 20)

		ax[1, 2].imshow(pr_mask5, cmap='gray')
		ax[1, 2].set_title('Model 5', fontsize = 20)

		ax[2, 0].imshow(ensemble_mask, cmap='gray')
		ax[2, 0].set_title('Ensemble', fontsize = 20)

		ax[2, 1].imshow(ensemble_mask_post_HF, cmap='gray')
		ax[2, 1].set_title('Ensemble + HF', fontsize = 20)

		ax[2, 2].imshow(ensemble_mask_post_HF_EI, cmap='gray')
		ax[2, 2].set_title('Ensemble + HF + EI', fontsize = 20)

		for axis in ax.flat:
			axis.get_xaxis().set_visible(False)
			axis.get_yaxis().set_visible(False)

		fig.suptitle(str(path_.split('\\')[-1]), fontsize=25, fontweight = 'bold')
		fig.tight_layout()
				
		plt.savefig(path_save_mask_img + '/result_' + str(iter) +  '.png')
		# plt.show()
		plt.close()

		Separation_l_r_lung(ensemble_mask_post_HF_EI, img, path_, iter, path_save_comp_img)


if __name__ == '__main__':  
	app.run(main) 