export interface MajorOption {
  order: string;
  code: string;
  name: string;
  label: string;
}

const major = (order: string, code: string, name: string): MajorOption => ({
  order,
  code,
  name,
  label: `${order} - ( ${code} ) ${name}`,
});

export const MAJOR_OPTIONS = [
  major("01", "BF-E12", "Kỹ thuật thực phẩm (Chương trình tiên tiến)"),
  major("02", "BF-E19", "Kỹ thuật sinh học (Chương trình tiên tiến)"),
  major("03", "BF1", "Kỹ thuật Sinh học"),
  major("04", "BF2", "Kỹ thuật Thực phẩm"),
  major("05", "CH-E11", "Kỹ thuật Hóa dược (Chương trình tiên tiến)"),
  major("06", "CH-E20", "Hóa học Mỹ phẩm (Chương trình tiên tiến)"),
  major("07", "CH1", "Kỹ thuật Hóa học"),
  major("08", "CH2", "Hóa học"),
  major("09", "ED2", "Công nghệ giáo dục"),
  major("10", "ED3", "Quản lý giáo dục"),
  major("11", "ED5", "Tâm lý học công nghiệp và tổ chức"),
  major("12", "EE-E18", "Hệ thống điện và năng lượng tái tạo (Chương trình tiên tiến)"),
  major("13", "EE-E8", "Kỹ thuật Điều khiển - Tự động hóa (Chương trình tiên tiến)"),
  major("14", "EE-EP", "Tin học công nghiệp và Tự động hóa (Chương trình Việt-Pháp PFIEV)"),
  major("15", "EE1", "Kỹ thuật điện"),
  major("16", "EE2", "Kỹ thuật Điều khiển - Tự động hóa"),
  major("17", "EM-E13", "Phân tích kinh doanh (Chương trình tiên tiến)"),
  major("18", "EM-E14", "Logistics và Quản lý chuỗi cung ứng (Chương trình tiên tiến)"),
  major("19", "EM-E17", "Kế toán (Chương trình tiên tiến)"),
  major("20", "EM1", "Quản lý năng lượng"),
  major("21", "EM2", "Quản lý công nghiệp"),
  major("22", "EM3", "Quản trị kinh doanh"),
  major("23", "EM5", "Tài chính - Ngân hàng"),
  major("24", "ET-E16", "Truyền thông số và Kỹ thuật đa phương tiện (Chương trình tiên tiến)"),
  major("25", "ET-E4", "Kỹ thuật Điện tử - Viễn thông (Chương trình tiên tiến)"),
  major("26", "ET-E5", "Kỹ thuật Y sinh (Chương trình tiên tiến)"),
  major("27", "ET-E9", "Hệ thống nhúng thông minh và IoT (Chương trình tiên tiến)"),
  major("28", "ET-LUH", "Điện tử-Viễn thông - ĐH Leibniz Hannover (Đức)"),
  major("29", "ET1", "Điện tử và Viễn thông"),
  major("30", "ET2", "Kỹ thuật Y sinh"),
  major("31", "EV1", "Kỹ thuật Môi trường"),
  major("32", "EV2", "Quản lý Tài nguyên và Môi trường"),
  major("33", "FL1", "Tiếng Anh Khoa học Kỹ thuật và Công nghệ"),
  major("34", "FL2", "Tiếng Anh Chuyên nghiệp Quốc tế"),
  major("35", "FL3", "Tiếng Trung Khoa học và Công nghệ"),
  major("36", "FL4", "Tiếng Hàn Khoa học và Công nghệ"),
  major("37", "HE1", "Kỹ thuật Nhiệt"),
  major("38", "IT-E10", "Khoa học Dữ liệu và Trí tuệ Nhân tạo"),
  major("39", "IT-E15", "An toàn không gian số (Chương trình tiên tiến)"),
  major("40", "IT-E6", "Công nghệ thông tin (Việt-Nhật) (Chương trình tiên tiến)"),
  major("41", "IT-E7", "Công nghệ thông tin (Global ICT)"),
  major("42", "IT-EP", "Công nghệ thông tin (Việt-Pháp) (Chương trình tiên tiến)"),
  major("43", "IT1", "CNTT: Khoa học Máy tính"),
  major("44", "IT2", "CNTT: Kỹ thuật máy tính"),
  major("45", "ME-E1", "Kỹ thuật Cơ điện tử (Chương trình tiên tiến)"),
  major("46", "ME-GU", "Cơ khí - Chế tạo máy - ĐH Griffith (Úc)"),
  major("47", "ME-LUH", "Cơ điện tử - ĐH Leibniz Hannover (Đức)"),
  major("48", "ME-NUT", "Cơ điện tử - ĐH Nagaoka (Nhật Bản)"),
  major("49", "ME1", "Kỹ thuật Cơ điện tử"),
  major("50", "ME2", "Kỹ thuật Cơ khí"),
  major("51", "MI-E22", "Khoa học tính toán cho các hệ thống thông minh (CTTT)"),
  major("52", "MI1", "Toán - Tin"),
  major("53", "MI2", "Hệ thống thông tin quản lý"),
  major("54", "MS-E3", "Khoa học và Kỹ thuật Vật liệu (Chương trình tiên tiến)"),
  major("55", "MS1", "Kỹ thuật Vật liệu"),
  major("56", "MS2", "Chương trình Kỹ thuật vi điện tử và công nghệ Nano"),
  major("57", "MS3", "Công nghệ vật liệu polyme và compozit"),
  major("58", "MS5", "Kỹ thuật in"),
  major("59", "PH1", "Vật lý kỹ thuật"),
  major("60", "PH2", "Kỹ thuật hạt nhân"),
  major("61", "PH3", "Vật lý Y khoa"),
  major("62", "TE-E2", "Kỹ thuật Ô tô (Chương trình tiên tiến)"),
  major("63", "TE-EP", "Cơ khí hàng không (Chương trình Việt - Pháp PFIEV)"),
  major("64", "TE1", "Kỹ thuật Ô tô"),
  major("65", "TE2", "Kỹ thuật Cơ khí động lực"),
  major("66", "TE3", "Kỹ thuật Hàng không"),
  major("67", "TROY-IT", "Khoa học máy tính - ĐH Troy (Hoa Kỳ)"),
  major("68", "TX1", "Công nghệ Dệt May"),
] as const;

export const COHORT_OPTIONS = ["K70", "K69", "K68", "K67", "K66", "K65", "K64", "K63", "K62"] as const;

export const findMajorOptionByCode = (code: string | null | undefined) =>
  MAJOR_OPTIONS.find((option) => option.code === code);
