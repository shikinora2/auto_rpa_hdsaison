import { MobileOutlined, ClockCircleOutlined, ToolOutlined } from '@ant-design/icons';
import { Result, Typography } from 'antd';
import './SmsGateway.css';

const { Text } = Typography;

export default function SmsGateway() {
  return (
    <div className="sms-gateway-page">
      <div className="sms-gateway-coming-soon">
        <div className="sms-gateway-icon-wrap">
          <MobileOutlined className="sms-gateway-main-icon" />
        </div>
        <div className="sms-gateway-title">SMS Gateway</div>
        <div className="sms-gateway-subtitle">Tính năng đang được phát triển</div>
        <div className="sms-gateway-badges">
          <span className="sms-badge">
            <ClockCircleOutlined /> Sắp ra mắt
          </span>
          <span className="sms-badge">
            <ToolOutlined /> Đang xây dựng
          </span>
        </div>
        <div className="sms-gateway-desc">
          Tích hợp gửi &amp; nhận SMS tự động qua gateway.<br />
          Tính năng sẽ được bổ sung trong phiên bản tiếp theo.
        </div>
      </div>
    </div>
  );
}
