#include <rclcpp/rclcpp.hpp>
#include "hbm_img_msgs/msg/hbm_msg1080_p.hpp"
#include <opencv2/opencv.hpp>
#include <zbar.h>
#include <std_msgs/msg/int32.hpp>
#include <std_msgs/msg/string.hpp>
#include <chrono>

class Qrcode : public rclcpp::Node
{
public:
  Qrcode() : Node("qrcode"), number_i_(0)
  {
    rclcpp::QoS qos(1);
    qos.reliability(RMW_QOS_POLICY_RELIABILITY_BEST_EFFORT);
    subscriber_hbmem_ = this->create_subscription<hbm_img_msgs::msg::HbmMsg1080P>(
        "/nv12_img", qos, std::bind(&Qrcode::subscription_callback, this, std::placeholders::_1));
        
    // 发布方向信息（Int32, 3=顺时针 4=逆时针）
    qrcode_number_publisher_ = this->create_publisher<std_msgs::msg::Int32>("/qrcode_number", 10);
    // 发布原始解码内容（String, 如"1234" / "ClockWise" / "AntiClockWise"）
    qrcode_raw_publisher_ = this->create_publisher<std_msgs::msg::String>("/qrcode_raw", 10);

    // 冷却时间（秒），同一个码在此时间内不重复发布
    this->declare_parameter("cooldown", 5.0);
  }

private:
  void subscription_callback(const hbm_img_msgs::msg::HbmMsg1080P::SharedPtr msg)
  {
    if (!msg)
      return;
    
    int height = msg->height;
    int width = msg->width;
    size_t step = msg->step;
    cv::Mat y_plane(height, width, CV_8UC1, msg->data.data(), step);
    cv::Mat gray;
    if (static_cast<size_t>(width) == step) {
      gray = y_plane;
    } else {
      gray = y_plane.clone();
    }
    
    zbar::ImageScanner scanner;
    scanner.set_config(zbar::ZBAR_NONE, zbar::ZBAR_CFG_ENABLE, 1);
    zbar::Image zbar_image(width, height, "Y800", gray.data, width * height);
    int result = scanner.scan(zbar_image);
    
    if (result > 0)
    {
      for (zbar::Image::SymbolIterator symbol = zbar_image.symbol_begin(); symbol != zbar_image.symbol_end(); ++symbol)
      {
        std::string qr_data = symbol->get_data();

        // ── 防抖：同一个码在 cooldown 秒内只发一次 ──
        auto now = this->now();
        double cooldown = this->get_parameter("cooldown").as_double();
        if (qr_data == last_qr_data_ &&
            (now - last_publish_time_).seconds() < cooldown)
        {
          continue;  // 冷却期内，跳过
        }
        last_qr_data_ = qr_data;
        last_publish_time_ = now;
        // ── 防抖结束 ──
        
        std_msgs::msg::Int32 qrcode_number_msg;

        if (qr_data == "ClockWise") // 顺时针
        {
          qrcode_number_msg.data = 3; 
        }
        else if (qr_data == "AntiClockWise") // 逆时针
        {
          qrcode_number_msg.data = 4; 
        }
        else
        {
          try
          {
            int number = std::stoi(qr_data);
            if (number >= 1 && number <= 9999)
            {
              qrcode_number_msg.data = (number % 2 == 0) ? 4 : 3;
            }
            else
            {
              RCLCPP_WARN(this->get_logger(), "Recognized number out of range (1-9999): %d", number);
              continue;
            }
          }
          catch (const std::invalid_argument &e)
          {
            RCLCPP_WARN(this->get_logger(), "Unrecognized content: %s", qr_data.c_str());
            continue;
          }
        }

        qrcode_number_publisher_->publish(qrcode_number_msg);

        std_msgs::msg::String raw_msg;
        raw_msg.data = qr_data;
        qrcode_raw_publisher_->publish(raw_msg);
        RCLCPP_INFO(this->get_logger(), "QR: %s → dir=%d", qr_data.c_str(), qrcode_number_msg.data);
      }
    }
  }
  
  rclcpp::Subscription<hbm_img_msgs::msg::HbmMsg1080P>::SharedPtr subscriber_hbmem_;
  rclcpp::Publisher<std_msgs::msg::Int32>::SharedPtr qrcode_number_publisher_;
  rclcpp::Publisher<std_msgs::msg::String>::SharedPtr qrcode_raw_publisher_;
  int number_i_ = 0;

  // 防抖：记录上次扫到的码和发布时间
  std::string last_qr_data_;
  rclcpp::Time last_publish_time_;
};

int main(int argc, char *argv[])
{
  rclcpp::init(argc, argv);
  rclcpp::spin(std::make_shared<Qrcode>());
  rclcpp::shutdown();
  return 0;
}
