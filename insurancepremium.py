# -*- coding: utf-8 -*-
"""InsurancePremium.ipynb

Automatically generated by Colab.

Original file is located at
    https://colab.research.google.com/drive/15eyaOpn8TWcdzi7_Nzhsr5NdalUM3iSj
"""

from google.colab import drive
drive.mount('/content/drive')

import pandas as pd
import xgboost as xgb
from xgboost import XGBRegressor
from sklearn.metrics import mean_squared_error,root_mean_squared_log_error
from sklearn.preprocessing import OrdinalEncoder,OneHotEncoder, StandardScaler
from sklearn.compose import ColumnTransformer
from sklearn.pipeline import Pipeline
from sklearn.model_selection import GridSearchCV, RandomizedSearchCV, train_test_split
import matplotlib.pyplot as plt
import seaborn as sns
from sklearn.metrics import mean_squared_error
import numpy as np
from sklearn.impute import SimpleImputer

"""#Load Data"""

# Read CSV
train = pd.read_csv('/content/drive/My Drive/Colab Notebooks/Insurance_Premium/train.csv')
test = pd.read_csv('/content/drive/My Drive/Colab Notebooks/Insurance_Premium/test.csv')

# Check Missing Values
print('--- Train Missing Values % ---\n')
print(train.isna().sum()/train.shape[0]*100)
print('\n--- Test Missing Values % ---\n')
print(test.isna().sum()/test.shape[0]*100)

"""# EDA"""

# EDA
print(f'Train Shape:{train.shape}')
print(f'Test Shape:{test.shape}')
print(train.dtypes)
with pd.option_context('display.float_format', '{:.2f}'.format):
    print(train.describe())

# Visualization
# Target
plt.figure(figsize=(8, 6))
sns.kdeplot(data=train, x='Premium Amount', color='steelblue', fill=True)
plt.title("Premium Amount")
plt.xlabel("Premium Amount")
plt.ylabel("Density")
plt.show()

# Log Target
plt.figure(figsize=(8, 6))
sns.kdeplot(data=train, x=np.log(train['Premium Amount']), color='red', fill=True)
plt.title("Log-transformed 'Premium Amount")
plt.xlabel("Log(Premium Amount)")
plt.ylabel("Density")
plt.show()

X_train = train.drop(['id','Premium Amount'],axis=1)
y_train = train['Premium Amount'].apply(np.log1p)

"""# Missing Values Handling"""

# Handling Missing Annual Income & Occupation
age_w_missing_income = X_train.loc[(X_train['Annual Income'].isna()),'Age']
age_w_missing_income.hist(bins=20)
plt.show()

# Fill missing income for Missing Annual Income & Occupation based on age
X_train.loc[(X_train['Age']<=22) & (X_train['Annual Income'].isna()),'Annual Income'] = 0
X_train.loc[((X_train['Age']<=22) | (X_train['Age']>=60)) & (X_train['Occupation'].isna()),'Occupation'] = 'Unemployed'

# Fill missing Number of Dependents with 0.
X_train.loc[X_train['Number of Dependents'].isna(),'Number of Dependents'] = 0

# Transform start date to days
X_train['Days Since Start'] = (pd.to_datetime('today') - pd.to_datetime(X_train['Policy Start Date'])).dt.days

# convert days to tenre categories
def tenre_categories(x):
    if x <= 365:
      return 'New Customer'
    elif x <= 365*3:
      return 'Regular Customer'
    else:
      return 'Long Term Customer'

X_train['customer tenure'] = X_train['Days Since Start'].apply(tenre_categories)

X_train.drop(['Policy Start Date','Days Since Start'],axis=1,inplace=True)

# Fill missing customer feedback with 'Unknown'
X_train['Customer Feedback'].fillna('Unknown',inplace=True)

# Fill missing Previous Claims
X_train['Previous Claims'].fillna(0,inplace=True)

# Fill missing with median
cols = ['Annual Income','Credit Score','Health Score','Age']
imputer = SimpleImputer(strategy='median')
X_train[cols] = imputer.fit_transform(X_train[cols])

"""# Feature Encoding & Standardize"""

# column categorization and order mapping
num_cols = X_train.select_dtypes(include=['int','float']).columns.to_list()
cat_cols = ['Gender','Marital Status','Occupation','Location','Smoking Status','Property Type','Policy Type','Exercise Frequency']
ord_cols = {
    'Education Level':['High School',"Bachelor's","Master's",'PhD'],
    'Customer Feedback':['Poor','Average','Good','Unknown'],
    'customer tenure':['New Customer','Regular Customer','Long Term Customer']
}

# Ordinal Encoding
for col, order in ord_cols.items():
    encoder = OrdinalEncoder(categories=[order])
    X_train[col] = encoder.fit_transform(X_train[[col]])

# Drop Unknown from ordinal mapping
X_train.loc[X_train['Customer Feedback'] == 3,'Customer Feedback'] = np.nan


# One Hot Encoding
oh_encoder = OneHotEncoder(handle_unknown='ignore',sparse_output=False, drop='first')
oh_encode_col = oh_encoder.fit_transform(X_train[cat_cols])

one_hot_df = pd.DataFrame(oh_encode_col, columns=oh_encoder.get_feature_names_out(cat_cols))
X_train = pd.concat([X_train,one_hot_df],axis=1)

X_train.drop(cat_cols,axis=1,inplace=True)

# Standardize numerical cols
scaler = StandardScaler()
scaled_data = scaler.fit_transform(X_train[num_cols])
X_train[num_cols] = scaled_data

"""# Model Training

"""

# Define XGB
xgb_model = xgb.XGBRegressor(objective = 'reg:squarederror',
                             booster = 'gbtree',
                             tree_method='hist',
                             device='cuda',
                             n_jobs = -1,
                             verbosity = 2,
                             random_state = 123)

# Hyperparameter Tuning
# Randomized Search
param_dist = {
    'n_estimators':np.arange(100,1001,150),
    'learning_rate':np.arange(0.05,0.8,0.05),
    'max_depth':range(3,12),
    'subsample':np.arange(0,0.8,0.1),
    'colsample_bytree':np.arange(0,0.8,0.1),
    'gamma': np.arange(0, 0.5, 0.05),
    'reg_lambda':[0,1,10,50],
    'reg_alpha': [0,1,10,50]
}


random_search = RandomizedSearchCV(estimator=xgb_model,
                                   param_distributions=param_dist,
                                   scoring='neg_mean_squared_log_error',
                                   n_iter=25,
                                   cv=4,
                                   return_train_score=True,
                                   random_state=123)

# Fit model
random_search.fit(X_train, y_train)

# View the best parameters
print("Best parameters found: ", random_search.best_params_)
print("Best score found: ", random_search.best_score_)

# Access the best estimator found by RandomizedSearchCV
best_model = random_search.best_estimator_

# Make predictions on the training set (or test set if you prefer)
y_pred = best_model.predict(X_train)

# Back-transform predictions to original scale
y_pred_exp = np.expm1(y_pred)
y_train_exp = np.expm1(y_train)

# Print RMSLE on whole training set
rmsle = np.sqrt(mean_squared_error(np.log1p(y_train_exp), np.log1p(y_pred_exp)))
print(f"RMSLE (Root Mean Squared Logarithmic Error): {rmsle}")

# Show the sets used in RandomizedSearchCV
result = pd.DataFrame(random_search.cv_results_).sort_values(by='rank_test_score',ascending=True)
cols_interest=['param_subsample', 'param_reg_lambda', 'param_reg_alpha',
       'param_n_estimators', 'param_max_depth', 'param_learning_rate',
       'param_gamma', 'param_colsample_bytree', 'mean_test_score', 'mean_train_score','rank_test_score']
result[cols_interest]

if (y_train <= 0).any():
    print("Warning: There are non-positive values in the training data.")
if (y_pred <= 0).any():
    print("Warning: Negative or zero values in predictions.")

print(f"Min prediction: {y_pred.min()}, Max prediction: {y_pred.max()}")

xgb.plot_importance(best_model, importance_type='weight', max_num_features=19)
plt.show()

# Log
'''
Base line RMSE wo tuning: 863
RMSE: 863.1959846331615
{'objective': 'reg:squarederror', 'base_score': None, 'booster': None, 'callbacks': None, 'colsample_bylevel': None, 'colsample_bynode': None, 'colsample_bytree': None, 'device': None, 'early_stopping_rounds': None, 'enable_categorical': False, 'eval_metric': 'rmse', 'feature_types': None, 'gamma': None, 'grow_policy': None, 'importance_type': None, 'interaction_constraints': None, 'learning_rate': None, 'max_bin': None, 'max_cat_threshold': None, 'max_cat_to_onehot': None, 'max_delta_step': None, 'max_depth': None, 'max_leaves': None, 'min_child_weight': None, 'missing': nan, 'monotone_constraints': None, 'multi_strategy': None, 'n_estimators': None, 'n_jobs': None, 'num_parallel_tree': None, 'random_state': 123, 'reg_alpha': None, 'reg_lambda': None, 'sampling_method': None, 'scale_pos_weight': None, 'subsample': None, 'tree_method': None, 'validate_parameters': None, 'verbosity': None}

Best parameters found:  {'xgb__subsample': 0.9, 'xgb__reg_lambda': 0.1, 'xgb__n_estimators': 100, 'xgb__max_depth': 3, 'xgb__learning_rate': 0.25, 'xgb__colsample_bytree': 0.7}
Best score found:  0.0008560791859755964
RMSE: 864.4336927500087

-- After Feature Engineering
Base line RMSE wo tuning: 829

Best parameters found:  {'subsample': 0.4, 'reg_lambda': 50, 'n_estimators': 400, 'max_depth': 7, 'learning_rate': 0.05, 'colsample_bytree': 0.7}
Best score found:  0.05643512878547263
RMSE: 832.6364997071444

-- After transform target
Best parameters found:  {'subsample': 0.4, 'reg_lambda': 50, 'n_estimators': 400, 'max_depth': 7, 'learning_rate': 0.05, 'colsample_bytree': 0.7}
Best score found:  -1.1024721484768294
RMSE: 766.1151925821111

-- After fill NAs for important features
Best parameters found:  {'subsample': 0.30000000000000004, 'reg_lambda': 1, 'reg_alpha': 50, 'n_estimators': 250, 'max_depth': 10, 'learning_rate': 0.05, 'colsample_bytree': 0.4}
Best score found:  -1.1120848348514911
RMSE: 758.3805137832269

Best parameters found:  {'subsample': 0.5, 'reg_lambda': 50, 'reg_alpha': 1, 'n_estimators': 550, 'max_depth': 5, 'learning_rate': 0.15000000000000002, 'gamma': 0.1, 'colsample_bytree': 0.30000000000000004}
Best score found:  -0.02536451575643285
RMSLE (Root Mean Squared Logarithmic Error): 1.0485475281048025
'''