/// Task-oriented destinations in the local administrator console.
enum AdminDestination {
  dashboard('대시보드', '현재 확인할 항목을 살펴보세요'),
  transactions('거래 내역', '거래 기록을 찾고 확인하세요'),
  reviewInbox('검토함', '확인이 필요한 기록을 검토하세요'),
  products('상품 관리', '판매 상품 정보를 관리하세요'),
  diagnostics('시스템 진단', '기기와 추론 상태를 확인하세요'),
  settings('설정', '운영 설정을 확인하세요');

  const AdminDestination(this.label, this.description);

  final String label;
  final String description;
}
