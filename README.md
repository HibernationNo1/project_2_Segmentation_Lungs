# Mask R-CNN for Lung Segmentation

서울대학병원 융합의학과 김영곤 교수님의 과제 수행 repository입니다.

흉부 CT image로부터 letf, right lung을 구분하여 segmentation을 진행하는 모델을 구현했습니다.

- 학습에 필요한 dataset은 서울대학병원 융합의학과 김영곤 교수님의 [Research-Segmentation-Lung](https://github.com/younggon2/Research-Segmentation-Lung-CXR-COVID19)를 인용하여 코드의 수정을 통해  json file로 저장하도록 했습니다.
- 학습을 진행하는 model은  https://github.com/akTwelve/Mask_RCNN 로부터 수정을 통해 학습하고자 하는 dataset에 알맞도록 구현하였습니다.
- training, test dataset source
  - [chest-xray-pneumonia](https://www.kaggle.com/paultimothymooney/chest-xray-pneumonia)
  - [covid19-image-dataset](https://www.kaggle.com/pranavraikokte/covid19-image-dataset)




## Description

- [Create_Dataset.dm](https://github.com/HibernationNo1/assignment-Segmented_Lung/blob/master/description/Create%20Dataset.md)

  input image로부터 Mask R-CNN을 학습시키기 위한 label을 담고 있는 dataset 만드는 code에 대한 설명입니다.

- [Training.md](https://github.com/HibernationNo1/assignment-Segmented_Lung/blob/master/description/Training.md)

  흉부 CT dataset을 통해 Mask R-CNN의 학습을 진행하는 code에 대한 설명입니다.

- [Inference.md](https://github.com/HibernationNo1/assignment-Segmented_Lung/blob/master/description/Inference.md)

  학습된 모델을 통해 test dataset에 대해서 inference를 진행하는 code에 대한 설명입니다.



## Code

- [create_dataset.py](https://github.com/HibernationNo1/assignment-Segmented_Lung/blob/master/code/create_dataset/create_dataset.py)

  training 및 test dataset을 만들어내는 code입니다.

- [model.py](https://github.com/HibernationNo1/assignment-Segmented_Lung/blob/master/code/mask_rcnn/model.py), [utils.py](https://github.com/HibernationNo1/assignment-Segmented_Lung/blob/master/code/mask_rcnn/utils.py), [config.py](https://github.com/HibernationNo1/assignment-Segmented_Lung/blob/master/code/mask_rcnn/config.py)

  Mask R-CNN 구현한 code입니다.

  



## Segmentation result

Segmentation inference result

![](https://github.com/HibernationNo1/assignment-Segmented_Lung/blob/master/image/r5.png?raw=true)

![](https://github.com/HibernationNo1/assignment-Segmented_Lung/blob/master/image/r6.png?raw=true)



compare with original

![](https://github.com/HibernationNo1/assignment-Segmented_Lung/blob/master/image/r1.png?raw=true)

### Loss

![](https://github.com/HibernationNo1/assignment-Segmented_Lung/blob/master/image/loss.png?raw=true)





![](https://github.com/HibernationNo1/assignment-Segmented_Lung/blob/master/image/loss_1.png?raw=true)



### Model

model을 학습하는데 사용한 dataset은 아래와 같습니다.

**dataset** 

[chest-xray-pneumonia](https://www.kaggle.com/paultimothymooney/chest-xray-pneumonia)

train\NORMAL

무작위 50개의 image

\+

[covid19-image-dataset](https://www.kaggle.com/pranavraikokte/covid19-image-dataset)

train\Normal
무작위 50개의 image

총 100개의 image를 통해 dataset을 구성했습니다.



[**trained model**](https://github.com/HibernationNo1/assignment-Segmented_Lung/blob/master/model_mask-rcnn/lungs_model/mask_rcnn__lungs_0000.h5)

> 해당 model과 sample test image을 통해 바로 segmentation을 진행할 수 있는 code를 ipynb file로 업로드 하기 위해 version문제를 해결하고 있습니다.





## Requirements

### create_dataset.py

#### tools

| name   | version | note             |
| ------ | ------- | ---------------- |
| CUDA   | 11.0    | cudart64_110.dll |
| cuDNN  | 8.2     | cudnn64_8.dll    |
| python | 3.8.8   |                  |

#### package

| name                | version |
| ------------------- | ------- |
| segmentation_models | 1.0.1   |
| cv2                 | 4.5.3   |
| scipy               | 1.6.2   |
| numpy               | 1.21.2  |



### Mask RCNN

#### tools

| name   | version | note             |
| ------ | ------- | ---------------- |
| CUDA   | 10.0    | cudart64_100.dll |
| cuDNN  | 7.6.4   | cudnn64_7.dll    |
| python | 3.7.11  |                  |

#### package

| name             | version |
| ---------------- | ------- |
| tensorflow       | 2.0.0   |
| tensorflow.keras | 2.2.4   |
| h5py             | 2.10.0  |
| cv2              | 4.5.3   |
| skimage          | 0.16.2  |



