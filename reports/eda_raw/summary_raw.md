# EDA dữ liệu gốc - Craigslist Cars & Trucks

- Số dòng: **426,880**, số cột đọc vào: **23** (chưa tính description, image_url, region_url)

## 1. Tổng quan cột
                dtype  pct_missing  n_unique
county        float64       100.00         0
size           object        71.77         4
cylinders      object        41.62         8
condition      object        40.79         6
VIN            object        37.73    118264
drive          object        30.59         3
paint_color    object        30.50        12
type           object        21.75        13
manufacturer   object         4.13        42
title_status   object         1.93         6
lat           float64         1.53     53181
long          float64         1.53     53772
model          object         1.24     29667
odometer      float64         1.03    104870
fuel           object         0.71         5
transmission   object         0.60         3
year          float64         0.28       114
posting_date   object         0.02    381536
region         object         0.00       404
price           int64         0.00     15655
id              int64         0.00    426880
url            object         0.00    426880
state          object         0.00        51

- Dòng thiếu đồng thời year + manufacturer + model + odometer: 68
- Cột county thiếu 100.0% -> loại bỏ hoàn toàn

## 2. Biến mục tiêu price
count          426,880
mean            75,199
std         12,182,282
min                  0
1%                   0
5%                   0
10%                500
25%              5,900
50%             13,950
75%             26,486
90%             37,590
95%             44,500
99%             66,995
99.9%          120,000
max      3,736,928,711
- price <= 0: 32,895 dòng (7.71%)
- price <= 500: 43,115 dòng (10.10%)
- price <= 1,000: 47,524 dòng (11.13%)
- price > 150,000: 196 dòng
- price > 1,000,000: 53 dòng
- 15 mức giá xuất hiện nhiều nhất (dấu hiệu định giá kiểu đại lý ...995, ...990):
price
0        32895
6995      3169
7995      3129
9995      2867
8995      2837
4500      2778
5995      2727
3500      2716
29990     2705
6500      2594
5500      2584
10995     2390
7500      2351
25990     2320
27990     2228

## 3. Loại người bán (trích từ URL: /ctd/ = dealer, /cto/ = owner)
seller_type
dealer    341989
owner      84891
- Trong 32,895 tin price = 0: dealer 32,618, owner 277 -> price=0 chủ yếu là 'liên hệ để biết giá' của đại lý

## 4. Năm sản xuất và số dặm
- year: min 1900, max 2022, thiếu 1,205
- year < 1990: 12,383 dòng (2.90%)
count       422,480
mean         98,043
std         213,882
min               0
1%                2
50%          85,548
99%         280,000
99.9%     1,111,111
max      10,000,000
- odometer = 0: 1,965; odometer > 400,000: 1,702
- Giá trị odometer lặp nhiều nhất (giá trị 'tròn' / giữ chỗ):
odometer
100000.0    2263
1.0         2246
0.0         1965
200000.0    1728
150000.0    1603
160000.0    1250
140000.0    1244
130000.0    1204

## 5. Biến phân loại

**condition**: (thiếu) 174,104, good 121,456, excellent 101,467, like new 21,178, fair 6,769, new 1,305, salvage 601

**cylinders**: (thiếu) 177,678, 6 cylinders 94,169, 4 cylinders 77,642, 8 cylinders 72,062, 5 cylinders 1,712, 10 cylinders 1,455, other 1,298, 3 cylinders 655, 12 cylinders 209

**fuel**: gas 356,209, other 30,728, diesel 30,062, hybrid 5,170, (thiếu) 3,013, electric 1,698

**title_status**: clean 405,117, (thiếu) 8,242, rebuilt 7,219, salvage 3,868, lien 1,422, missing 814, parts only 198

**transmission**: automatic 336,524, other 62,682, manual 25,118, (thiếu) 2,556

**drive**: 4wd 131,904, (thiếu) 130,567, fwd 105,517, rwd 58,892

**size**: (thiếu) 306,361, full-size 63,465, mid-size 34,476, compact 19,384, sub-compact 3,194

**type**: (thiếu) 92,858, sedan 87,056, SUV 77,284, pickup 43,510, truck 35,279, other 22,110, coupe 19,204, hatchback 16,598, wagon 10,751, van 8,548, convertible 7,731, mini-van 4,825, offroad 609, bus 517

**paint_color**: (thiếu) 130,203, white 79,285, black 62,861, silver 42,970, blue 31,223, red 30,473, grey 24,416, green 7,343, custom 6,700, brown 6,593, yellow 2,142, orange 1,984, purple 687

- manufacturer: 42 hãng; 5 hãng lớn nhất chiếm 46.99%
- model: 29,667 giá trị khác nhau (viết tự do, rất bẩn). Ví dụ: e-class e300; wrangler unlimited all new; cx-5; del sol si; odyssey ex-l; 7 series; outback; patriot

## 6. Trùng lặp
- Trùng id: 0
- Có VIN: 265,838 dòng, 118,264 VIN khác nhau -> 147,574 dòng đăng lặp cùng một chiếc xe
- VIN bị đăng nhiều nhất: 261 lần (1FMJU1JT1HEA52352), trải trên 253 khu vực -> đại lý đăng tràn lan
- Trong các VIN lặp, 8.90% có nhiều mức giá khác nhau (đổi giá khi đăng lại) -> giữ tin mới nhất
- Trùng toàn bộ nội dung chính (không xét VIN): 128,283
- Số TIN ĐĂNG theo nhóm lặp: 1 lần: 77,984, 2 lần: 35,792, 3 lần: 22,893, 4-5 lần: 32,983, 6-10 lần: 34,232, 11-20 lần: 23,105, 21-50 lần: 21,755, > 50 lần: 17,094

## 7. Thời gian đăng tin và tọa độ
- posting_date: từ 2021-04-04 07:00:25+00:00 đến 2021-05-05 04:24:09+00:00 -> chọn SCRAPE_YEAR = 2021
- Tọa độ nằm ngoài lãnh thổ Mỹ: 176 dòng -> đặt NaN

## 8. Quan hệ sơ bộ (chỉ xét 1000 <= price <= 150k)
- Giá trung vị giảm dần khi xe cũ hơn, nhưng xe trước ~1990 giá lại TĂNG (xe sưu tầm)