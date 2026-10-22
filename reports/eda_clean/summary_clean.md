# EDA dữ liệu sạch

- 198,514 dòng x 48 cột; 2,348 cặp hãng+dòng xe, 53 hãng
- 91.0% số dòng thuộc nhóm hãng+dòng+năm có >= 10 xe (dùng để tính giá tương đối)

## 1. Biến mục tiêu
- Độ lệch (skewness): price = 2.01, log(1+price) = -0.18 -> nên train trên log_price rồi đổi ngược bằng expm1

## 2. Khấu hao theo tuổi và số dặm
- Giá trung vị theo tuổi: 0 năm: $38,615, 3 năm: $26,990, 6 năm: $17,500, 9 năm: $10,900, 12 năm: $6,999, 15 năm: $5,985, 18 năm: $4,800, 21 năm: $4,477, 24 năm: $4,500, 27 năm: $5,500, 30 năm: $6,700
- chevrolet silverado: sau 5 năm còn ~67%, sau 10 năm còn ~37% giá trị (so với xe 1 tuổi)
- ford f150: sau 5 năm còn ~65%, sau 10 năm còn ~33% giá trị (so với xe 1 tuổi)
- ram 1500: sau 5 năm còn ~65%, sau 10 năm còn ~38% giá trị (so với xe 1 tuổi)
- jeep wrangler: sau 5 năm còn ~68%, sau 10 năm còn ~45% giá trị (so với xe 1 tuổi)

## 3. Tương quan Spearman với giá
car_age           -0.727
odometer          -0.633
long              -0.151
lat               -0.038
posting_dow       -0.025
miles_per_year     0.071
n_unknown_specs    0.103
cylinders_num      0.236
condition_rank     0.257
has_vin            0.305
desc_len           0.467

## 4. Giá trung vị theo biến phân loại
- type: pickup $22,998, truck $20,000, other $19,998, coupe $13,800, van $13,599, offroad $13,500, suv $13,212, convertible $12,978, wagon $10,995, unknown $9,950, hatchback $9,292, sedan $8,999, mini-van $6,995
- condition: new $23,900, like new $15,000, unknown $14,997, excellent $10,999, good $8,500, salvage $3,500, fair $2,999
- fuel: diesel $26,995, other $21,990, electric $18,987, unknown $17,995, gas $10,997, hybrid $9,995
- drive: 4wd $16,899, rwd $14,000, unknown $10,995, fwd $8,950
- transmission: other $24,590, unknown $16,986, automatic $11,823, manual $8,950
- title_status: lien $18,000, unknown $14,989, clean $11,999, rebuilt $9,999, salvage $7,500, missing $2,600
- seller_type: dealer $14,995, owner $7,000
- brand_tier: exotic $83,500, luxury $14,995, mainstream $11,500
- cylinders: 8 cylinders $15,900, unknown $14,977, 10 cylinders $12,994, other $12,780, 6 cylinders $10,990, 3 cylinders $9,992, 4 cylinders $8,995, 5 cylinders $6,350
- paint_color: white $15,493, orange $14,925, black $14,445, yellow $12,900, custom $12,197, red $11,278, unknown $11,000, grey $10,990, silver $10,425, blue $9,995, brown $8,996, purple $7,992, green $6,995

## 5. Đại lý vs chính chủ (giá tương đối trong cùng hãng+dòng+năm)
- Giá tương đối trung vị: dealer 1.014, owner 0.920 -> cùng một mẫu xe, đại lý niêm yết cao hơn chính chủ khoảng 10%
- (Lưu ý: xe đại lý có odometer trung vị 93,885 so với 130,000 của chính chủ -> một phần chênh lệch đến từ số dặm)

## 6. Ảnh hưởng của từ khóa trong mô tả (giá tương đối có / không có từ khóa)
- Tính trên 180,682 tin thuộc nhóm hãng+dòng+năm có >= 10 xe; CI 95% bootstrap 300 lần
                nhan  so_tin_co  pct_tin_co  pct_tin_dai_ly  chenh_lech_pct  ci95_thap  ci95_cao  chenh_lech_owner_pct  chenh_lech_dealer_pct
Cần sửa / không chạy        982        0.54           21.28          -45.95     -48.07    -43.95                -44.85                 -22.35
             Lốp mới      12688        7.02           43.47           -1.40      -2.14     -0.77                  2.54                  -1.03
          Camera lùi      32305       17.88           87.01            1.52       1.08      1.90                  5.21                   1.19
             Một chủ      20829       11.53           83.32            2.30       1.89      2.60                  9.36                   1.42
            Bảo hành      48943       27.09           96.04            3.16       2.84      3.47                 10.58                   2.24
        Lịch sử sạch      21423       11.86           82.87            4.33       3.96      4.68                  9.38                   4.52
         Cửa sổ trời      33165       18.36           74.98            4.97       4.68      5.28                  9.17                   6.63
              Ghế da      50806       28.12           78.89            6.09       5.72      6.40                 11.09                   6.01
             Định vị      25706       14.23           83.93            6.28       5.99      6.66                  9.69                   7.00
      Hỗ trợ trả góp      79091       43.77           98.83            6.73       6.38      7.04                  5.39                   3.33
              Ít dặm      15482        8.57           79.82            7.76       7.33      8.23                 19.91                   6.89
            Nâng gầm       5796        3.21           88.99           10.31       9.59     11.10                 20.77                   9.18

## 7. Bang rẻ / đắt nhất (giá tương đối trung vị, bang có >= 1000 tin)
- Rẻ nhất: NJ 0.935, MI 0.936, CT 0.936, MD 0.937, OH 0.943
- Đắt nhất: ID 1.097, HI 1.115, WA 1.117, OR 1.126, AK 1.132

## 8. Tỷ lệ 'unknown' còn lại ở biến phân loại
condition       38.08
cylinders       34.48
drive           26.96
type            24.83
paint_color     27.70
fuel             0.58
title_status     1.27
transmission     0.36